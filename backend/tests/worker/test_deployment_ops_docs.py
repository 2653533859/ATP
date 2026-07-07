from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_compose_worker_uses_configurable_celery_queues():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    worker = compose["services"]["worker"]

    assert "CELERY_QUEUES=${CELERY_QUEUES:-default,mobile_special,ai,maintenance,performance}" in worker["environment"]
    assert "-Q $${CELERY_QUEUES}" in worker["command"]


def test_helm_values_expose_worker_queues_and_resources():
    values = yaml.safe_load((ROOT / "deploy" / "helm" / "atp" / "values.yaml").read_text(encoding="utf-8"))

    assert values["worker"]["queues"] == "default,mobile_special,ai,maintenance,performance"
    assert values["config"]["CELERY_QUEUES"] == "default,mobile_special,ai,maintenance,performance"
    assert values["performanceWorker"]["enabled"] is False
    assert values["performanceWorker"]["queues"] == "performance"
    assert values["performanceWorker"]["concurrency"] == "1"
    assert values["performanceWorker"]["resources"]["requests"]
    assert values["performanceWorker"]["resources"]["limits"]
    assert values["hpa"]["performanceWorker"]["enabled"] is False
    for component in ("backend", "worker", "beat", "flower"):
        assert values["resources"][component]["requests"]
        assert values["resources"][component]["limits"]


def test_helm_chart_can_render_dedicated_performance_worker():
    content = (ROOT / "deploy" / "helm" / "atp" / "templates" / "performance-worker-deployment.yaml").read_text(
        encoding="utf-8"
    )
    hpa = (ROOT / "deploy" / "helm" / "atp" / "templates" / "hpa.yaml").read_text(encoding="utf-8")
    schema = json.loads((ROOT / "deploy" / "helm" / "atp" / "values.schema.json").read_text(encoding="utf-8"))

    assert "{{- if .Values.performanceWorker.enabled }}" in content
    assert "app.kubernetes.io/component: performance-worker" in content
    assert "CELERY_QUEUES" in content
    assert ".Values.performanceWorker.queues" in content
    assert ".Values.performanceWorker.resources" in content
    assert ".Values.performanceWorker.metricsPort" in content
    assert "hpa.performanceWorker" in hpa
    assert "performanceWorker" in schema["properties"]


def test_worker_dockerfile_bundles_k6_for_performance_queue():
    content = (ROOT / "backend" / "Dockerfile.worker").read_text(encoding="utf-8")

    assert "ARG K6_IMAGE=grafana/k6:" in content
    assert "FROM ${K6_IMAGE} AS k6-bin" in content
    assert "COPY --from=k6-bin /usr/bin/k6 /usr/local/bin/k6" in content
    assert "k6 version" in content


def test_grafana_dashboard_contains_slow_query_rate_panel():
    dashboard = json.loads(
        (ROOT / "docker" / "grafana" / "dashboards" / "atp-overview.json").read_text(encoding="utf-8")
    )

    titles = {panel["title"] for panel in dashboard["panels"]}
    assert "Slow query rate" in titles
    assert any(
        target.get("expr") == "rate(atp_slow_queries_total[5m])"
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    )


def test_celery_queue_runbook_exists():
    content = (ROOT / "docs" / "celery-queues.md").read_text(encoding="utf-8")

    assert "default" in content
    assert "mobile_special" in content
    assert "maintenance" in content
    assert "performance" in content
    assert "run_performance_test" in content
    assert "grafana/k6" in content
