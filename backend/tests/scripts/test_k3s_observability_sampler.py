"""Contract tests for the bounded K3s observability sampler."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]


def _load_sampler():
    path = ROOT / "scripts" / "k3s-observability-sampler.py"
    spec = importlib.util.spec_from_file_location("k3s_observability_sampler", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Client:
    def json(self, *args):
        if "nodes" in args:
            return {
                "items": [
                    {
                        "metadata": {"name": "node-a"},
                        "status": {
                            "conditions": [
                                {"type": "Ready", "status": "True"},
                                {"type": "MemoryPressure", "status": "False"},
                                {"type": "DiskPressure", "status": "False"},
                                {"type": "PIDPressure", "status": "False"},
                            ]
                        },
                    }
                ]
            }
        return {
            "items": [
                {
                    "metadata": {
                        "name": f"atp-{component}",
                        "labels": {"app.kubernetes.io/component": component},
                    },
                    "status": {
                        "phase": "Running",
                        "containerStatuses": [{"ready": True, "restartCount": 0}],
                    },
                }
                for component in ("backend", "worker", "performance-worker")
            ]
        }

    def raw(self, path):
        if path.endswith("/nodes"):
            return '{"items":[{"metadata":{"name":"node-a"},"usage":{"cpu":"100m","memory":"1Gi"}}]}'
        if path.endswith("/pods"):
            return (
                '{"items":['
                '{"metadata":{"name":"atp-backend"},"containers":[{"usage":{"cpu":"10m","memory":"10Mi"}}]},'
                '{"metadata":{"name":"atp-worker"},"containers":[{"usage":{"cpu":"20m","memory":"20Mi"}}]},'
                '{"metadata":{"name":"atp-performance-worker"},"containers":[{"usage":{"cpu":"30m","memory":"30Mi"}}]}'
                "]}"
            )
        return (
            "# TYPE process_resident_memory_bytes gauge\nprocess_resident_memory_bytes 42\natp_run_outcomes_total 1\n"
        )


def test_collect_sample_covers_nodes_pods_resources_and_required_metrics():
    sampler = _load_sampler()

    sample = sampler.collect_sample(_Client(), namespace="atp", selector="app=atp")

    assert sample["alerts"] == []
    assert sample["nodes"][0]["usage"] == {"cpu_millicores": 100, "memory_bytes": 1073741824}
    assert {item["component"] for item in sample["pods"]} == {
        "backend",
        "worker",
        "performance-worker",
    }
    assert sample["metrics"]["backend"]["atp_metric_families"] == ["atp_run_outcomes_total"]


def test_collect_sample_records_not_ready_restarts_and_missing_metrics():
    sampler = _load_sampler()
    client = _Client()
    original_json = client.json

    def unhealthy_json(*args):
        payload = original_json(*args)
        if "pods" in args:
            payload["items"][0]["status"]["containerStatuses"][0].update(ready=False, restartCount=2)
            payload["items"] = payload["items"][:2]
        return payload

    client.json = unhealthy_json
    original_raw = client.raw

    def incomplete_metrics(path):
        value = original_raw(path)
        if path.endswith("/nodes"):
            return '{"items":[]}'
        if path.endswith("/pods"):
            value = value.replace(
                ',{"metadata":{"name":"atp-worker"},"containers":[{"usage":{"cpu":"20m","memory":"20Mi"}}]}',
                "",
            )
        return value

    client.raw = incomplete_metrics
    sample = sampler.collect_sample(client, namespace="atp", selector="app=atp")

    assert "pod_not_ready:atp-backend" in sample["alerts"]
    assert "pod_restarts:atp-backend:2" in sample["alerts"]
    assert "node_metrics_missing:node-a" in sample["alerts"]
    assert "component_missing:performance-worker" in sample["alerts"]
    assert "pod_metrics_missing:atp-worker" in sample["alerts"]


def test_build_report_fails_when_a_required_component_is_not_covered_every_time():
    sampler = _load_sampler()
    args = argparse.Namespace(
        source_revision="abc123",
        context="single-node",
        namespace="atp",
        selector="app=atp",
        duration_seconds=10,
        interval_seconds=5,
    )
    samples = [
        {"metrics": {"backend": {}, "worker": {}, "performance-worker": {}}, "alerts": []},
        {"metrics": {"backend": {}, "worker": {}}, "alerts": ["metrics_unavailable:performance-worker"]},
    ]

    report = sampler.build_report(args, samples)

    assert report["status"] == "failed"
    assert report["scope"]["source_revision"] == "abc123"
    assert report["summary"]["missing_required_components"] == ["performance-worker"]
    assert report["secrets_included"] is False


def test_sample_until_collects_immediately_and_at_the_duration_boundary(monkeypatch):
    sampler = _load_sampler()
    timeline = iter([0.0, 0.0, 5.0, 10.0])
    monkeypatch.setattr(sampler.time, "monotonic", lambda: next(timeline))
    sleeps = []

    samples = sampler.sample_until(
        lambda: {"sample": True}, duration_seconds=10, interval_seconds=5, sleep=sleeps.append
    )

    assert len(samples) == 3
    assert sleeps == [5, 5]
