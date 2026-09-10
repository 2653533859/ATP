"""Collect bounded, redacted observability evidence from an ATP Kubernetes release.

The sampler uses only ``kubectl`` and the Kubernetes API proxy.  It is intended
for single-node integration environments where Prometheus Operator is not
available; it does not claim to replace release-grade Prometheus history.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable
from urllib.parse import quote


COMPONENT_PORTS = {"backend": 8000, "worker": 9091, "performance-worker": 9092}
REQUIRED_COMPONENTS = tuple(COMPONENT_PORTS)
_METRIC_NAME = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)")


class SamplingError(RuntimeError):
    """Raised when required Kubernetes or metrics evidence cannot be collected."""


class Kubectl:
    def __init__(self, *, binary: str = "kubectl", context: str | None = None) -> None:
        self.prefix = [binary]
        if context:
            self.prefix.extend(["--context", context])

    def text(self, *args: str) -> str:
        try:
            completed = subprocess.run(
                [*self.prefix, *args],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=20,
            )
        except subprocess.TimeoutExpired as exc:
            raise SamplingError(f"kubectl {' '.join(args[:3])} timed out after 20 seconds") from exc
        except OSError as exc:
            raise SamplingError(f"cannot execute kubectl: {str(exc)[:300]}") from exc
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip().replace("\n", " ")[:500]
            raise SamplingError(f"kubectl {' '.join(args[:3])} failed: {detail or 'unknown error'}")
        return completed.stdout

    def json(self, *args: str) -> dict[str, Any]:
        try:
            value = json.loads(self.text(*args))
        except json.JSONDecodeError as exc:
            raise SamplingError(f"kubectl {' '.join(args[:3])} returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise SamplingError("kubectl JSON response must be an object")
        return value

    def raw(self, path: str) -> str:
        return self.text("get", "--raw", path)


def _condition_status(conditions: list[dict[str, Any]], condition_type: str) -> str | None:
    for condition in conditions:
        if condition.get("type") == condition_type:
            return str(condition.get("status"))
    return None


def _memory_bytes(value: str) -> int:
    """Convert a Kubernetes memory quantity to bytes."""
    raw = str(value).strip()
    suffixes = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "K": 1000,
        "M": 1000**2,
        "G": 1000**3,
    }
    for suffix in sorted(suffixes, key=len, reverse=True):
        if raw.endswith(suffix):
            return int(float(raw[: -len(suffix)]) * suffixes[suffix])
    return int(float(raw))


def _cpu_millicores(value: str) -> int:
    """Convert a Kubernetes CPU quantity to integer millicores."""
    raw = str(value).strip()
    if raw.endswith("n"):
        return int(float(raw[:-1]) / 1_000_000)
    if raw.endswith("u"):
        return int(float(raw[:-1]) / 1_000)
    if raw.endswith("m"):
        return int(float(raw[:-1]))
    return int(float(raw) * 1000)


def _metric_summary(body: str) -> dict[str, Any]:
    names: set[str] = set()
    sample_count = 0
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _METRIC_NAME.match(stripped)
        if match:
            names.add(match.group(1))
            sample_count += 1
    if not names:
        raise SamplingError("metrics endpoint returned no Prometheus samples")
    return {
        "sample_count": sample_count,
        "metric_family_count": len(names),
        "atp_metric_families": sorted(name for name in names if name.startswith("atp_")),
        "process_metric_present": "process_resident_memory_bytes" in names,
    }


def _pod_snapshot(pod: dict[str, Any], usage: dict[str, dict[str, int]]) -> dict[str, Any]:
    metadata = pod.get("metadata", {})
    status = pod.get("status", {})
    name = str(metadata.get("name", ""))
    container_statuses = status.get("containerStatuses") or []
    return {
        "name": name,
        "component": (metadata.get("labels") or {}).get("app.kubernetes.io/component"),
        "phase": status.get("phase"),
        "ready": bool(container_statuses) and all(item.get("ready") is True for item in container_statuses),
        "restarts": sum(int(item.get("restartCount") or 0) for item in container_statuses),
        "usage": usage.get(name),
    }


def _resource_usage(payload: dict[str, Any], *, pods: bool) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for item in payload.get("items") or []:
        name = str((item.get("metadata") or {}).get("name", ""))
        rows = item.get("containers") or [] if pods else [item.get("usage") or {}]
        cpu = (
            sum(_cpu_millicores(row.get("usage", {}).get("cpu", "0")) for row in rows)
            if pods
            else _cpu_millicores(rows[0].get("cpu", "0"))
        )
        memory = (
            sum(_memory_bytes(row.get("usage", {}).get("memory", "0")) for row in rows)
            if pods
            else _memory_bytes(rows[0].get("memory", "0"))
        )
        result[name] = {"cpu_millicores": cpu, "memory_bytes": memory}
    return result


def collect_sample(client: Kubectl, *, namespace: str, selector: str) -> dict[str, Any]:
    nodes = client.json("get", "nodes", "-o", "json")
    pods = client.json("-n", namespace, "get", "pods", "-l", selector, "-o", "json")
    node_metrics = client.raw("/apis/metrics.k8s.io/v1beta1/nodes")
    pod_metrics = client.raw(f"/apis/metrics.k8s.io/v1beta1/namespaces/{quote(namespace, safe='')}/pods")
    node_usage = _resource_usage(json.loads(node_metrics), pods=False)
    pod_usage = _resource_usage(json.loads(pod_metrics), pods=True)

    node_rows = []
    alerts: list[str] = []
    for node in nodes.get("items") or []:
        metadata = node.get("metadata") or {}
        conditions = (node.get("status") or {}).get("conditions") or []
        name = str(metadata.get("name", ""))
        ready = _condition_status(conditions, "Ready") == "True"
        pressure = [
            item
            for item in ("MemoryPressure", "DiskPressure", "PIDPressure")
            if _condition_status(conditions, item) == "True"
        ]
        if not ready:
            alerts.append(f"node_not_ready:{name}")
        if name not in node_usage:
            alerts.append(f"node_metrics_missing:{name}")
        alerts.extend(f"node_pressure:{name}:{item}" for item in pressure)
        node_rows.append({"name": name, "ready": ready, "pressure": pressure, "usage": node_usage.get(name)})

    pod_rows = [_pod_snapshot(item, pod_usage) for item in pods.get("items") or []]
    for pod in pod_rows:
        if not pod["ready"]:
            alerts.append(f"pod_not_ready:{pod['name']}")
        if pod["restarts"]:
            alerts.append(f"pod_restarts:{pod['name']}:{pod['restarts']}")
        if pod["name"] not in pod_usage:
            alerts.append(f"pod_metrics_missing:{pod['name']}")

    by_component = {row["component"]: row for row in pod_rows if row.get("component")}
    metrics: dict[str, dict[str, Any]] = {}
    for component, port in COMPONENT_PORTS.items():
        pod = by_component.get(component)
        if not pod:
            alerts.append(f"component_missing:{component}")
            continue
        path = (
            f"/api/v1/namespaces/{quote(namespace, safe='')}/pods/"
            f"{quote(str(pod['name']), safe='')}:{port}/proxy/metrics"
        )
        try:
            metrics[component] = _metric_summary(client.raw(path))
        except SamplingError as exc:
            alerts.append(f"metrics_unavailable:{component}:{exc}")

    return {
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "nodes": node_rows,
        "pods": pod_rows,
        "metrics": metrics,
        "alerts": alerts,
    }


def sample_until(
    collector: Callable[[], dict[str, Any]],
    *,
    duration_seconds: float,
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    started = time.monotonic()
    while True:
        samples.append(collector())
        elapsed = time.monotonic() - started
        if elapsed >= duration_seconds:
            break
        sleep(min(interval_seconds, max(duration_seconds - elapsed, 0)))
    return samples


def build_report(args: argparse.Namespace, samples: list[dict[str, Any]]) -> dict[str, Any]:
    alert_count = sum(len(sample["alerts"]) for sample in samples)
    covered = sorted(set.intersection(*(set(sample["metrics"]) for sample in samples))) if samples else []
    missing = sorted(set(REQUIRED_COMPONENTS) - set(covered))
    return {
        "evidence_type": "k3s_bounded_observability",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if not alert_count and not missing else "failed",
        "scope": {
            "source_revision": args.source_revision,
            "context": args.context,
            "namespace": args.namespace,
            "selector": args.selector,
            "duration_seconds": args.duration_seconds,
            "interval_seconds": args.interval_seconds,
        },
        "summary": {
            "sample_count": len(samples),
            "alert_count": alert_count,
            "metrics_components_covered_every_sample": covered,
            "missing_required_components": missing,
        },
        "samples": samples,
        "boundary": "Bounded single-node sampling is integration evidence, not release-grade Prometheus history or P4 closure.",
        "secrets_included": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context")
    parser.add_argument("--source-revision", default="unknown")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--duration-seconds", type=float, default=60)
    parser.add_argument("--interval-seconds", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.duration_seconds < 0 or args.interval_seconds <= 0:
        parser.error("duration must be non-negative and interval must be positive")
    return args


def main() -> int:
    args = parse_args()
    client = Kubectl(context=args.context)
    try:
        samples = sample_until(
            lambda: collect_sample(client, namespace=args.namespace, selector=args.selector),
            duration_seconds=args.duration_seconds,
            interval_seconds=args.interval_seconds,
        )
        report = build_report(args, samples)
    except (SamplingError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[{report['status'].upper()}] samples={report['summary']['sample_count']} "
        f"alerts={report['summary']['alert_count']} output={args.output}"
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
