from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def _load_deployment_validator():
    path = ROOT / "scripts" / "validate-deployment-readiness.py"
    spec = importlib.util.spec_from_file_location("validate_deployment_readiness", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deployment_validator_skips_shell_check_when_posix_shell_is_unavailable(monkeypatch):
    validator = _load_deployment_validator()
    monkeypatch.setattr(validator.shutil, "which", lambda _name: None)
    skipped: list[str] = []
    failures: list[str] = []

    validator._check_shell_scripts(False, skipped, failures)

    assert failures == []
    assert skipped == ["shell syntax (sh/bash is not available)"]


def test_deployment_validator_can_require_a_posix_shell(monkeypatch):
    validator = _load_deployment_validator()
    monkeypatch.setattr(validator.shutil, "which", lambda _name: None)
    skipped: list[str] = []
    failures: list[str] = []

    validator._check_shell_scripts(True, skipped, failures)

    assert skipped == []
    assert failures == ["shell syntax (sh/bash is not available)"]


def test_compose_worker_uses_configurable_celery_queues():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    worker = compose["services"]["worker"]

    assert "CELERY_QUEUES=${CELERY_QUEUES:-default,android,mobile_special,ios,ai,maintenance,performance}" in worker["environment"]
    assert "-Q $${CELERY_QUEUES}" in worker["command"]


def test_helm_values_expose_worker_queues_and_resources():
    values = yaml.safe_load((ROOT / "deploy" / "helm" / "atp" / "values.yaml").read_text(encoding="utf-8"))

    assert values["worker"]["queues"] == "default,ios,ai,maintenance,performance"
    assert values["config"]["CELERY_QUEUES"] == "default,ios,ai,maintenance,performance"
    assert values["performanceWorker"]["enabled"] is False
    assert values["performanceWorker"]["queues"] == "performance"
    assert values["performanceWorker"]["concurrency"] == "1"
    assert values["performanceWorker"]["nodeEnabled"] is True
    assert values["performanceWorker"]["nodeId"] == ""
    assert values["performanceWorker"]["nodeQueue"] == "performance"
    assert values["performanceWorker"]["networkPolicy"]["enabled"] is False
    assert values["performanceWorker"]["resources"]["requests"]
    assert values["performanceWorker"]["resources"]["limits"]
    assert values["hpa"]["performanceWorker"]["enabled"] is False
    for component in ("backend", "worker", "beat", "flower"):
        assert values["resources"][component]["requests"]
        assert values["resources"][component]["limits"]


def test_helm_production_overlays_have_secret_and_metrics_hooks():
    values = yaml.safe_load((ROOT / "deploy" / "helm" / "atp" / "values.yaml").read_text(encoding="utf-8"))
    secret = (ROOT / "deploy" / "helm" / "atp" / "templates" / "secret.yaml").read_text(encoding="utf-8")
    helpers = (ROOT / "deploy" / "helm" / "atp" / "templates" / "_helpers.tpl").read_text(encoding="utf-8")
    service_monitor = (ROOT / "deploy" / "helm" / "atp" / "templates" / "servicemonitor.yaml").read_text(
        encoding="utf-8"
    )
    ingress = (ROOT / "deploy" / "helm" / "atp" / "templates" / "ingress.yaml").read_text(encoding="utf-8")

    assert values["secret"] == {"create": True, "existingName": ""}
    assert secret.lstrip().startswith("{{- if .Values.secret.create }}")
    assert "if .Values.secret.create" in secret
    assert 'define "atp.secretName"' in helpers
    assert ".Values.secret.existingName" in helpers
    assert "monitoring.coreos.com/v1" in service_monitor
    assert ".Values.metrics.serviceMonitor.enabled" in service_monitor
    assert "path: /metrics" in service_monitor
    assert "force-ssl-redirect" in ingress


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
    assert ".Values.performanceWorker.nodeId" in content
    assert ".Values.performanceWorker.nodeQueue" in content
    assert 'queues="${CELERY_QUEUES:-performance}"' in content
    assert 'queues="${queues},performance"' in content
    assert "readinessProbe" in content
    assert "livenessProbe" in content
    network_policy = (
        ROOT / "deploy" / "helm" / "atp" / "templates" / "performance-worker-network-policy.yaml"
    ).read_text(encoding="utf-8")
    assert "kind: NetworkPolicy" in network_policy
    assert ".Values.performanceWorker.networkPolicy.egress" in network_policy
    assert "hpa.performanceWorker" in hpa
    assert "performanceWorker" in schema["properties"]


def test_worker_dockerfile_bundles_k6_for_performance_queue():
    content = (ROOT / "backend" / "Dockerfile.worker").read_text(encoding="utf-8")

    assert "ARG K6_IMAGE=grafana/k6:" in content
    assert "FROM ${K6_IMAGE} AS k6-bin" in content
    assert "COPY --from=k6-bin /usr/bin/k6 /usr/local/bin/k6" in content
    assert "k6 version" in content
    assert "locust --version" in content
    assert "import grpc, grpc_tools" in content


def test_docker_compose_acceptance_stack_isolated_and_has_real_targets():
    compose = yaml.safe_load((ROOT / "docker-compose.performance-acceptance.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert compose["name"] == "atp-performance-acceptance"
    assert {"postgres", "redis", "minio", "backend", "performance-worker", "acceptance-target"} <= services.keys()
    assert services["backend"]["ports"] == ["127.0.0.1:18080:8000"]
    assert services["performance-worker"]["environment"]["PERFORMANCE_NODE_ID"] == "worker-a"
    assert services["performance-worker"]["environment"]["PERFORMANCE_NODE_QUEUE"] == "performance.worker-a"
    assert "grpc-target" in services["acceptance-target"]["networks"]["default"]["aliases"]
    assert "http-target" in services["acceptance-target"]["networks"]["default"]["aliases"]
    tls_command = " ".join(services["acceptance-tls"]["command"])
    assert "chown 10001:10001 /certs/server.crt /certs/server.key" in tls_command
    performance_command = " ".join(services["performance-worker"]["command"])
    assert 'queues="$${CELERY_QUEUES:-performance}"' in performance_command
    assert 'queues="$${queues},performance"' in performance_command
    assert "acceptance_tls:/etc/atp/tls:ro" in services["performance-worker"]["volumes"]
    assert "./docs/evidence:/evidence" in services["acceptance-tools"]["volumes"]
    assert (ROOT / "deploy" / "performance-acceptance" / "acceptance.proto").is_file()
    assert (ROOT / "deploy" / "performance-acceptance" / "locust_smoke.py").is_file()


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
