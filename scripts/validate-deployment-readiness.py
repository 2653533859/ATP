"""Validate repository-local deployment and disaster-recovery prerequisites."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "deploy/helm/atp/Chart.yaml",
    "deploy/helm/atp/values.yaml",
    "deploy/helm/atp/values.schema.json",
    "deploy/helm/atp/templates/servicemonitor.yaml",
    "deploy/grafana/alerts/atp-alerts.yaml",
    "docker/grafana/dashboards/atp-overview.json",
    "docker-compose.yml",
    "docker-compose.app.yml",
    "docker-compose.dev.yml",
    "backend/docker-start.sh",
    "backend/app/migration_startup.py",
    "docs/deploy-helm.md",
    "docs/external-infra-run.md",
    "docs/disaster-recovery.md",
    "docs/backup-restore-drill-record.md",
    "scripts/backup-postgres.sh",
    "scripts/restore-postgres.sh",
    "scripts/validate-android-worker-config.py",
    "config/deployment-profiles/android-worker-backend.env.example",
    "deploy/helm/atp/values-android-worker.example.yaml",
    "deploy/helm/atp/values-performance-acceptance.example.yaml",
    "deploy/helm/atp/values-performance-single-node.example.yaml",
    "deploy/performance-acceptance/minio-dr.env.example",
)


def _run(command: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode == 0, output


def _check_required_files(failures: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            failures.append(f"missing required file: {relative}")


def _check_data_files(failures: list[str]) -> None:
    yaml_files = (
        "deploy/helm/atp/values.yaml",
        "deploy/helm/atp/values-performance-acceptance.example.yaml",
        "deploy/helm/atp/values-performance-single-node.example.yaml",
        "docker-compose.yml",
        "docker-compose.app.yml",
        "docker-compose.dev.yml",
    )
    json_files = (
        "deploy/helm/atp/values.schema.json",
        "docker/grafana/dashboards/atp-overview.json",
    )
    for relative in yaml_files:
        try:
            yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            failures.append(f"invalid YAML {relative}: {exc}")
    for relative in json_files:
        try:
            json.loads((ROOT / relative).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"invalid JSON {relative}: {exc}")


def _resolve_shell() -> str | None:
    """Return a POSIX shell available on the current host, if any."""
    for candidate in ("sh", "bash"):
        shell = shutil.which(candidate)
        if shell:
            return shell
    return None


def _check_shell_scripts(require_shell: bool, skipped: list[str], failures: list[str]) -> None:
    shell = _resolve_shell()
    if shell is None:
        message = "shell syntax (sh/bash is not available)"
        (failures if require_shell else skipped).append(message)
        return

    for relative in ("backend/docker-start.sh", "scripts/backup-postgres.sh", "scripts/restore-postgres.sh"):
        ok, output = _run([shell, "-n", relative])
        if not ok:
            failures.append(f"shell syntax failed for {relative}: {output}")


def _check_document_contracts(failures: list[str]) -> None:
    deploy_doc = (ROOT / "docs/deploy-helm.md").read_text(encoding="utf-8")
    recovery_doc = (ROOT / "docs/disaster-recovery.md").read_text(encoding="utf-8")
    deploy_markers = (
        "PostgreSQL / Redis / MinIO",
        "ExternalSecrets / SOPS",
        "Ingress TLS",
        "Prometheus",
        "Grafana",
        "Beat 单副本 + Recreate",
        "alembic migration",
        "resources.requests/limits",
    )
    recovery_markers = (
        "pg-backups/daily/",
        "pg-backups/weekly/",
        'mc mirror --overwrite --exclude "pg-backups/*"',
        "scripts/restore-postgres.sh",
        "alembic upgrade head",
        "Backend `/health`",
        "historical report lookup",
        "docs/backup-restore-drill-record.md",
    )
    for marker in deploy_markers:
        if marker not in deploy_doc:
            failures.append(f"deployment checklist missing: {marker}")
    for marker in recovery_markers:
        if marker not in recovery_doc:
            failures.append(f"disaster-recovery runbook missing: {marker}")


def _read_env_template(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _check_android_worker_profiles(failures: list[str]) -> None:
    """Ensure server and Windows Agent profiles cannot silently consume the same queue."""
    env_path = ROOT / "config/deployment-profiles/android-worker-backend.env.example"
    overlay_path = ROOT / "deploy/helm/atp/values-android-worker.example.yaml"
    if not env_path.is_file() or not overlay_path.is_file():
        return

    server_env = _read_env_template(env_path)
    server_queues = {item.strip().lower() for item in server_env.get("CELERY_QUEUES", "").split(",") if item.strip()}
    if server_env.get("ADB_SCAN_MODE", "").strip().lower() != "worker":
        failures.append("Android Worker server profile must set ADB_SCAN_MODE=worker")
    if server_env.get("ADB_SCAN_ENABLED", "").strip().lower() not in {"1", "true", "yes"}:
        failures.append("Android Worker server profile must enable ADB_SCAN_ENABLED")
    if server_env.get("ANDROID_WORKER_QUEUE", "").strip() != "mobile_special":
        failures.append("Android Worker server profile must route to mobile_special")
    if server_queues & {"android", "mobile_special"}:
        failures.append("Android Worker server profile must exclude android,mobile_special")

    try:
        overlay = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        failures.append(f"invalid Android Worker Helm overlay: {exc}")
        return
    config = overlay.get("config") or {}
    worker = overlay.get("worker") or {}
    overlay_queues = {item.strip().lower() for item in str(config.get("CELERY_QUEUES", "")).split(",") if item.strip()}
    if config.get("ADB_SCAN_MODE") != "worker":
        failures.append("Android Worker Helm overlay must set config.ADB_SCAN_MODE=worker")
    if str(config.get("ADB_SCAN_ENABLED", "")).lower() not in {"1", "true", "yes"}:
        failures.append("Android Worker Helm overlay must enable config.ADB_SCAN_ENABLED")
    if config.get("ANDROID_WORKER_QUEUE") != "mobile_special":
        failures.append("Android Worker Helm overlay must route to mobile_special")
    if overlay_queues & {"android", "mobile_special"} or worker.get("queues") != config.get("CELERY_QUEUES"):
        failures.append("Android Worker Helm overlay must keep Linux Worker queues separate from Android queues")


def _check_single_node_performance_overlay(failures: list[str]) -> None:
    """Keep the K3s development overlay distinct from the multi-node release overlay."""
    overlay_path = ROOT / "deploy/helm/atp/values-performance-single-node.example.yaml"
    if not overlay_path.is_file():
        return
    try:
        overlay = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        failures.append(f"invalid single-node performance Helm overlay: {exc}")
        return

    image = overlay.get("image") or {}
    worker = overlay.get("worker") or {}
    config = overlay.get("config") or {}
    performance_worker = overlay.get("performanceWorker") or {}
    metrics = overlay.get("metrics") or {}
    service_monitor = metrics.get("serviceMonitor") or {}
    hpa = overlay.get("hpa") or {}
    ingress = overlay.get("ingress") or {}
    secret = overlay.get("secret") or {}

    image_components = (image.get("backend") or {}, image.get("worker") or {}, image.get("frontend") or {})
    if any(component.get("pullPolicy") != "Never" for component in image_components):
        failures.append("single-node performance Helm overlay must use imagePullPolicy Never for imported images")
    if performance_worker.get("enabled") is not True or performance_worker.get("replicas") != 1:
        failures.append("single-node performance Helm overlay must enable exactly one performance Worker")
    if performance_worker.get("autoIdentity") is not False or performance_worker.get("spreadAcrossNodes") is not False:
        failures.append("single-node performance Helm overlay must disable multi-node worker scheduling")
    if performance_worker.get("nodeId") != "atp-single-node" or (
        performance_worker.get("nodeQueue") != "performance.atp-single-node"
    ):
        failures.append("single-node performance Helm overlay must use the atp-single-node identity and queue")
    if "performance" in {item.strip().lower() for item in str(worker.get("queues", "")).split(",") if item.strip()}:
        failures.append("single-node performance Helm overlay must keep the default Worker off the performance queue")
    if config.get("CELERY_QUEUES") != worker.get("queues"):
        failures.append("single-node performance Helm overlay must keep default Worker queues aligned")
    if service_monitor.get("enabled") is not False:
        failures.append("single-node performance Helm overlay must disable ServiceMonitor without its CRD")
    if any(
        (hpa.get(component) or {}).get("enabled") is not False
        for component in ("backend", "worker", "performanceWorker")
    ):
        failures.append("single-node performance Helm overlay must disable HPA for fixed-capacity development")
    if ingress.get("enabled") is not False:
        failures.append("single-node performance Helm overlay must disable ingress until a controller is installed")
    if secret != {"create": False, "existingName": "atp-single-node-secrets"}:
        failures.append("single-node performance Helm overlay must reference the external development Secret")


def _compose_services(compose: Any, relative: str, failures: list[str]) -> dict[str, Any] | None:
    if not isinstance(compose, dict) or not isinstance(compose.get("services"), dict):
        failures.append(f"{relative} must define a services mapping")
        return None
    return compose["services"]


def _depends_on_healthy(service: dict[str, Any], dependency: str) -> bool:
    depends_on = service.get("depends_on")
    return (
        isinstance(depends_on, dict)
        and isinstance(depends_on.get(dependency), dict)
        and depends_on[dependency].get("condition") == "service_healthy"
    )


def _has_backend_healthcheck(service: dict[str, Any]) -> bool:
    healthcheck = service.get("healthcheck")
    if not isinstance(healthcheck, dict):
        return False
    probe = healthcheck.get("test")
    return isinstance(probe, list) and "/health" in " ".join(str(part) for part in probe)


def _validate_compose_startup_contracts(
    default_services: dict[str, Any], external_services: dict[str, Any], failures: list[str]
) -> None:
    """Reject regressions that can recreate an unbounded startup restart loop."""
    migrate = default_services.get("migrate")
    backend = default_services.get("backend")
    if not isinstance(migrate, dict) or migrate.get("command") != ["migrate"]:
        failures.append("docker-compose.yml migrate service must use the bounded migrate entrypoint")
    if not isinstance(backend, dict):
        failures.append("docker-compose.yml must define a backend service")
    else:
        if backend.get("command") != ["serve", "--skip-migrations"]:
            failures.append("docker-compose.yml backend must skip duplicate migrations after the migration gate")
        depends_on = backend.get("depends_on")
        migration_gate = (
            isinstance(depends_on, dict)
            and isinstance(depends_on.get("migrate"), dict)
            and depends_on["migrate"].get("condition") == "service_completed_successfully"
        )
        if not migration_gate:
            failures.append("docker-compose.yml backend must wait for a successful migration gate")
        if not _has_backend_healthcheck(backend):
            failures.append("docker-compose.yml backend must expose a /health healthcheck")

    external_backend = external_services.get("backend")
    if not isinstance(external_backend, dict):
        failures.append("docker-compose.app.yml must define a backend service")
    else:
        if external_backend.get("command") is not None:
            failures.append("docker-compose.app.yml backend must use the migration-owning image default command")
        if external_backend.get("restart") != "on-failure:3":
            failures.append("docker-compose.app.yml backend restart policy must remain bounded")
        if not _has_backend_healthcheck(external_backend):
            failures.append("docker-compose.app.yml backend must expose a /health healthcheck")

    for service_name in ("frontend", "worker", "web-recorder", "beat", "flower"):
        service = external_services.get(service_name)
        if not isinstance(service, dict) or not _depends_on_healthy(service, "backend"):
            failures.append(f"docker-compose.app.yml {service_name} must wait for backend health")


def _check_compose_startup_contracts(failures: list[str]) -> None:
    try:
        default_compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
        external_compose = yaml.safe_load((ROOT / "docker-compose.app.yml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        failures.append(f"cannot read Compose startup contracts: {exc}")
        return

    default_services = _compose_services(default_compose, "docker-compose.yml", failures)
    external_services = _compose_services(external_compose, "docker-compose.app.yml", failures)
    if default_services is not None and external_services is not None:
        _validate_compose_startup_contracts(default_services, external_services, failures)


def _resolve_compose() -> list[str] | None:
    configured = os.environ.get("COMPOSE")
    if configured:
        return shlex.split(configured)

    legacy = shutil.which("docker-compose")
    if legacy:
        return [legacy]

    docker = shutil.which("docker")
    if docker:
        ok, _ = _run([docker, "compose", "version"])
        if ok:
            return [docker, "compose"]
    return None


def _check_compose(require_compose: bool, skipped: list[str], failures: list[str]) -> None:
    compose = _resolve_compose()
    if compose is None:
        message = "Compose config (neither COMPOSE, docker-compose, nor docker compose is available)"
        (failures if require_compose else skipped).append(message)
        return
    if not (ROOT / ".env").is_file():
        message = "Compose config (.env is not present; use deployment credentials locally)"
        (failures if require_compose else skipped).append(message)
        return
    commands = (
        (
            "docker-compose.yml with docker-compose.dev.yml",
            ["-f", "docker-compose.yml", "-f", "docker-compose.dev.yml"],
        ),
        ("docker-compose.app.yml", ["-f", "docker-compose.app.yml"]),
    )
    for label, files in commands:
        ok, output = _run([*compose, *files, "config", "--quiet"])
        if not ok:
            failures.append(f"docker-compose config failed for {label}: {output}")


def _check_helm(require_helm: bool, skipped: list[str], failures: list[str]) -> None:
    helm = shutil.which("helm")
    if helm is None:
        message = "helm lint (helm is not installed)"
        (failures if require_helm else skipped).append(message)
        return
    ok, output = _run([helm, "lint", "deploy/helm/atp"])
    if not ok:
        failures.append(f"helm lint failed: {output}")


def _chart_fingerprint(chart: Path) -> dict[str, str]:
    if not chart.is_dir():
        raise ValueError("chart directory is missing")
    return {
        path.relative_to(chart).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in chart.rglob("*")
        if path.is_file()
    }


def _helm_capture(command: list[str], *, input_text: str | None = None) -> str:
    completed = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        timeout=60,
    )
    if completed.returncode:
        # Helm output may include rendered Secrets or values; never print it.
        raise RuntimeError(f"Helm {command[1]} failed with exit {completed.returncode}")
    return completed.stdout


def _manifest_index(content: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for resource in yaml.safe_load_all(content):
        if not isinstance(resource, dict):
            continue
        metadata = resource.get("metadata") or {}
        name = metadata.get("name")
        kind = resource.get("kind")
        if not isinstance(name, str) or not isinstance(kind, str):
            raise ValueError("rendered resource has no kind/name")
        identity = f"{kind}/{name}"
        if identity in result:
            raise ValueError(f"duplicate rendered resource: {identity}")
        result[identity] = resource
    return result


def _is_hook(resource: dict[str, Any]) -> bool:
    return bool(((resource.get("metadata") or {}).get("annotations") or {}).get("helm.sh/hook"))


def _memory_bytes(quantity: str) -> int:
    match = re.fullmatch(r"(\d+)(Mi|Gi)", quantity)
    if match is None:
        raise ValueError("Flower memory limit must use Mi or Gi")
    return int(match.group(1)) * (1024**2 if match.group(2) == "Mi" else 1024**3)


def _check_flower_manifest(resources: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    flowers = [
        item
        for item in resources.values()
        if item.get("kind") == "Deployment"
        and (item.get("metadata", {}).get("labels") or {}).get("app.kubernetes.io/component") == "flower"
    ]
    if len(flowers) != 1:
        return ["candidate must render exactly one Flower Deployment"]
    flower = flowers[0]
    spec = flower.get("spec") or {}
    pod = (spec.get("template") or {}).get("spec") or {}
    containers = [item for item in pod.get("containers", []) if item.get("name") == "flower"]
    if len(containers) != 1:
        return ["Flower Deployment must have exactly one Flower container"]
    container = containers[0]
    args = container.get("args") or []
    for flag, maximum in (("max_tasks", 1000), ("max_workers", 100), ("purge_offline_workers", 300)):
        values = [
            arg.removeprefix(f"--{flag}=") for arg in args if isinstance(arg, str) and arg.startswith(f"--{flag}=")
        ]
        if len(values) != 1 or not values[0].isdigit() or not 1 <= int(values[0]) <= maximum:
            failures.append(f"Flower --{flag} must be bounded between 1 and {maximum}")
    limit = ((container.get("resources") or {}).get("limits") or {}).get("memory")
    try:
        if not isinstance(limit, str) or _memory_bytes(limit) < 512 * 1024**2:
            failures.append("Flower memory limit must be at least 512Mi")
    except ValueError as exc:
        failures.append(str(exc))
    if pod.get("hostNetwork"):
        strategy = spec.get("strategy") or {}
        rollout = strategy.get("rollingUpdate") or {}
        safe = strategy.get("type") == "Recreate" or (
            strategy.get("type") == "RollingUpdate"
            and rollout.get("maxSurge") == 0
            and rollout.get("maxUnavailable") == "100%"
        )
        if not safe:
            failures.append("hostNetwork Flower must release port 5555 before starting its replacement")
    return failures


def _image_tags(resource: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    if resource is None:
        return ()
    spec = resource.get("spec") or {}
    containers = ((spec.get("template") or {}).get("spec") or {}).get("containers") or []
    tags = []
    for item in containers:
        basename = item.get("image", "").rsplit("/", 1)[-1]
        tags.append((item.get("name", ""), basename.rsplit(":", 1)[-1] if ":" in basename else "(untagged)"))
    return tuple(sorted(tags))


def _changes(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> list[tuple[str, str, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]]:
    result = []
    for identity in sorted(before.keys() | after.keys()):
        old, new = before.get(identity), after.get(identity)
        if old != new:
            status = "added" if old is None else "removed" if new is None else "changed"
            result.append((status, identity, _image_tags(old), _image_tags(new)))
    return result


def _changed_paths(old: Any, new: Any, prefix: str = "") -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        paths = []
        for key in sorted(old.keys() | new.keys()):
            paths.extend(_changed_paths(old.get(key), new.get(key), f"{prefix}.{key}" if prefix else key))
        return paths
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        paths = []
        for index, (before, after) in enumerate(zip(old, new, strict=True)):
            paths.extend(_changed_paths(before, after, f"{prefix}[{index}]"))
        return paths
    return [prefix] if old != new else []


def _image_tag_overrides(items: list[str]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in items:
        component, separator, tag = item.partition("=")
        if (
            not separator
            or component not in {"backend", "worker", "frontend"}
            or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag)
            or tag.lower() == "latest"
            or component in tags
        ):
            raise ValueError("--image-tag must be a unique backend/worker/frontend=tag (latest is rejected)")
        tags[component] = tag
    return tags


def _check_release_chart(
    *,
    release: str,
    namespace: str,
    chart: Path,
    allowed_changes: set[str],
    allowed_hooks: set[str],
    skip_hooks: bool,
    image_tags: dict[str, str] | None = None,
    values_files: list[Path] | None = None,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    report: list[str] = []
    source = ROOT / "deploy" / "helm" / "atp"
    try:
        source_files = _chart_fingerprint(source)
        candidate_files = _chart_fingerprint(chart)
    except (OSError, ValueError) as exc:
        return [f"Chart cannot be read: {exc}"], report
    if source_files != candidate_files:
        changed = sorted(
            source_files.keys() ^ candidate_files.keys()
            | {
                name
                for name in source_files.keys() & candidate_files.keys()
                if source_files[name] != candidate_files[name]
            }
        )
        return ["staged Chart differs from this repository: " + ", ".join(changed)], report
    report.append(f"PASS Chart matches repository ({len(source_files)} files)")

    helm = shutil.which("helm")
    if helm is None:
        return ["Helm is not installed"], report
    try:
        values = _helm_capture([helm, "get", "values", release, "-n", namespace, "-o", "yaml"])
        current_text = _helm_capture([helm, "get", "manifest", release, "-n", namespace])
        hooks_text = _helm_capture([helm, "get", "hooks", release, "-n", namespace])
        template_command = [helm, "template", release, str(chart), "-n", namespace, "-f", "-"]
        for path in values_files or []:
            template_command.extend(["-f", str(path)])
        for component, tag in sorted((image_tags or {}).items()):
            template_command.extend(["--set-string", f"image.{component}.tag={tag}"])
        candidate_text = _helm_capture(template_command, input_text=values)
        current = _manifest_index(current_text)
        old_hooks = _manifest_index(hooks_text)
        candidate_all = _manifest_index(candidate_text)
    except (OSError, subprocess.TimeoutExpired, RuntimeError, yaml.YAMLError, ValueError):
        return ["Helm release preflight could not render or parse manifests; inspect secure operator logs"], report
    candidate = {key: item for key, item in candidate_all.items() if not _is_hook(item)}
    new_hooks = {key: item for key, item in candidate_all.items() if _is_hook(item)}
    flower_failures = _check_flower_manifest(candidate)
    failures.extend(flower_failures)
    if not flower_failures:
        report.append("PASS Flower bounds and hostNetwork rollout strategy")
    for status, identity, old_images, new_images in _changes(current, candidate):
        report.append(f"RESOURCE {status} {identity}")
        if identity.startswith("Deployment/") and identity in current and identity in candidate:
            paths = _changed_paths(current[identity], candidate[identity])
            report.append(f"FIELDS {identity} " + ", ".join(paths[:20]) + (", ..." if len(paths) > 20 else ""))
        if old_images != new_images:
            report.append(f"IMAGE_TAG {identity} {old_images} -> {new_images}")
        if identity not in allowed_changes:
            failures.append(f"unreviewed resource change: {identity}")
    for status, identity, old_images, new_images in _changes(old_hooks, new_hooks):
        report.append(f"HOOK {status} {identity}" + (" (upgrade --no-hooks)" if skip_hooks else ""))
        if old_images != new_images:
            report.append(f"HOOK_IMAGE_TAG {identity} {old_images} -> {new_images}")
        if not skip_hooks and identity not in allowed_hooks:
            failures.append(f"unreviewed migration hook change: {identity}")
    report.append(f"PASS rendered resource inventory: {len(candidate)} regular, {len(new_hooks)} hooks")
    return failures, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-helm",
        action="store_true",
        help="fail when Helm is unavailable; use this on a release operator workstation",
    )
    parser.add_argument(
        "--require-shell",
        action="store_true",
        help="fail when sh/bash is unavailable; use this on a release operator workstation",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when any environment-dependent check is skipped; use this before a real release",
    )
    parser.add_argument("--release", help="preflight an existing Helm release against the repository Chart")
    parser.add_argument("--namespace", default="atp-single-node", help="Helm release namespace")
    parser.add_argument("--chart", type=Path, default=ROOT / "deploy" / "helm" / "atp")
    parser.add_argument("--allow-change", action="append", default=[], metavar="KIND/NAME")
    parser.add_argument("--allow-hook-change", action="append", default=[], metavar="KIND/NAME")
    parser.add_argument("--skip-hooks", action="store_true", help="preflight an upgrade that will use --no-hooks")
    parser.add_argument("--image-tag", action="append", default=[], metavar="COMPONENT=TAG")
    parser.add_argument("--values-file", action="append", type=Path, default=[], metavar="PATH")
    args = parser.parse_args()

    if args.release:
        try:
            image_tags = _image_tag_overrides(args.image_tag)
        except ValueError as exc:
            parser.error(str(exc))
        failures, report = _check_release_chart(
            release=args.release,
            namespace=args.namespace,
            chart=args.chart,
            allowed_changes=set(args.allow_change),
            allowed_hooks=set(args.allow_hook_change),
            skip_hooks=args.skip_hooks,
            image_tags=image_tags,
            values_files=args.values_file,
        )
        for item in report:
            print(item)
        for item in failures:
            print(f"FAIL {item}", file=sys.stderr)
        return 1 if failures else 0

    failures: list[str] = []
    skipped: list[str] = []
    _check_required_files(failures)
    _check_data_files(failures)
    strict = args.strict
    _check_shell_scripts(strict or args.require_shell, skipped, failures)
    _check_document_contracts(failures)
    _check_android_worker_profiles(failures)
    _check_single_node_performance_overlay(failures)
    _check_compose_startup_contracts(failures)
    _check_compose(strict, skipped, failures)
    _check_helm(strict or args.require_helm, skipped, failures)

    for item in REQUIRED_FILES:
        if (ROOT / item).is_file():
            print(f"PASS file {item}")
    if skipped:
        for item in skipped:
            print(f"SKIP {item}")
    if failures:
        for item in failures:
            print(f"FAIL {item}", file=sys.stderr)
        return 1
    if skipped:
        print(
            f"PASS repository checks ({len(skipped)} environment-dependent check(s) skipped; use --strict to require them)"
        )
    else:
        print("PASS deployment and disaster-recovery repository checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
