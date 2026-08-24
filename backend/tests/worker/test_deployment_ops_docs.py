from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

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


def test_deployment_validator_strict_mode_requires_compose(monkeypatch):
    validator = _load_deployment_validator()
    monkeypatch.setattr(validator, "_resolve_compose", lambda: None)
    skipped: list[str] = []
    failures: list[str] = []

    validator._check_compose(True, skipped, failures)

    assert skipped == []
    assert failures == ["Compose config (neither COMPOSE, docker-compose, nor docker compose is available)"]


def test_deployment_validator_optional_compose_is_explicitly_skipped(monkeypatch):
    validator = _load_deployment_validator()
    monkeypatch.setattr(validator, "_resolve_compose", lambda: None)
    skipped: list[str] = []
    failures: list[str] = []

    validator._check_compose(False, skipped, failures)

    assert failures == []
    assert skipped == ["Compose config (neither COMPOSE, docker-compose, nor docker compose is available)"]


def test_deployment_validator_normalizes_missing_and_malformed_process_output(monkeypatch):
    validator = _load_deployment_validator()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1, stdout=None, stderr="\ufffd shell output")

    monkeypatch.setattr(validator.subprocess, "run", fake_run)

    ok, output = validator._run(["sh", "-n", "scripts/backup-postgres.sh"])

    assert ok is False
    assert output == "\ufffd shell output"
    assert calls[0][1]["errors"] == "replace"


def test_compose_worker_uses_configurable_celery_queues():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    worker = compose["services"]["worker"]

    assert (
        "CELERY_QUEUES=${CELERY_QUEUES:-default,android,mobile_special,ios,ai,maintenance,performance}"
        in worker["environment"]
    )
    assert "-Q $${CELERY_QUEUES}" in worker["command"]


def test_compose_can_start_an_independent_web_recording_worker():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    recorder = compose["services"]["web-recorder"]

    assert recorder["profiles"] == ["web-recorder"]
    assert recorder["environment"]
    assert "WEB_RECORDER_MODE=worker" in recorder["environment"]
    assert "python -m app.web_recording_worker" in recorder["command"][-1]
    assert "Xvfb" in recorder["command"][-1]
    assert any("WEB_RECORDER_HEALTH_FILE" in value for value in recorder["environment"])
    assert recorder["healthcheck"]["test"][0] == "CMD"


def test_compose_minio_lifecycle_requires_explicit_profile():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    lifecycle = compose["services"]["minio-lifecycle"]

    assert lifecycle["profiles"] == ["storage-lifecycle"]
    assert lifecycle["command"] == "python -m app.ops_minio_lifecycle"
    assert "MINIO_LIFECYCLE_APPLY=true" in lifecycle["environment"]
    assert lifecycle["restart"] == "no"
    assert lifecycle["depends_on"]["minio"]["condition"] == "service_healthy"


def test_helm_values_expose_worker_queues_and_resources():
    values = yaml.safe_load((ROOT / "deploy" / "helm" / "atp" / "values.yaml").read_text(encoding="utf-8"))

    assert values["worker"]["queues"] == "default,ios,ai,maintenance,performance"
    assert values["config"]["CELERY_QUEUES"] == "default,ios,ai,maintenance,performance"
    assert values["performanceWorker"]["enabled"] is False
    assert values["performanceWorker"]["queues"] == "performance"
    assert values["performanceWorker"]["concurrency"] == "1"
    assert values["performanceWorker"]["nodeEnabled"] is True
    assert values["performanceWorker"]["autoIdentity"] is False
    assert values["performanceWorker"]["nodeId"] == ""
    assert values["performanceWorker"]["nodeQueue"] == "performance"
    assert values["performanceWorker"]["networkPolicy"]["enabled"] is False
    assert values["performanceWorker"]["resources"]["requests"]
    assert values["performanceWorker"]["resources"]["limits"]
    assert values["service"]["performanceWorker"]["type"] == "ClusterIP"
    assert values["service"]["performanceWorker"]["port"] == 9092
    assert values["replicas"]["webRecorder"] == 1
    assert values["webRecorder"]["enabled"] is False
    assert values["webRecorder"]["maxSessions"] == 2
    assert values["webRecorder"]["healthFile"] == "/tmp/atp-web-recorder.ready"
    assert values["config"]["WEB_RECORDER_MODE"] == "local"
    assert values["hpa"]["performanceWorker"]["enabled"] is False
    for component in ("backend", "worker", "beat", "flower"):
        assert values["resources"][component]["requests"]
        assert values["resources"][component]["limits"]


def test_helm_android_worker_overlay_separates_linux_and_windows_queues():
    overlay = yaml.safe_load(
        (ROOT / "deploy" / "helm" / "atp" / "values-android-worker.example.yaml").read_text(encoding="utf-8")
    )
    content = (ROOT / "docs" / "deploy-helm.md").read_text(encoding="utf-8")

    assert overlay["worker"]["queues"] == "default,ios,ai,maintenance,performance"
    assert overlay["config"]["ADB_SCAN_ENABLED"] == "true"
    assert overlay["config"]["ADB_SCAN_MODE"] == "worker"
    assert overlay["config"]["ANDROID_WORKER_QUEUE"] == "mobile_special"
    assert overlay["config"]["CELERY_QUEUES"] == overlay["worker"]["queues"]
    assert overlay["secret"] == {"create": False, "existingName": "atp-runtime-secrets"}
    assert "android,mobile_special" not in overlay["worker"]["queues"]
    assert "values-android-worker.example.yaml" in content
    assert "config/startup-profiles/android-agent.env" in content


def test_deployment_readiness_validates_android_worker_profile_contract():
    validator = _load_deployment_validator()
    failures: list[str] = []

    validator._check_android_worker_profiles(failures)

    assert failures == []


def test_helm_exposes_opt_in_minio_lifecycle_reconciler():
    values = yaml.safe_load((ROOT / "deploy" / "helm" / "atp" / "values.yaml").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "deploy" / "helm" / "atp" / "values.schema.json").read_text(encoding="utf-8"))
    template = (ROOT / "deploy" / "helm" / "atp" / "templates" / "minio-lifecycle-job.yaml").read_text(encoding="utf-8")

    lifecycle = values["storageLifecycle"]
    assert lifecycle["enabled"] is False
    assert lifecycle["abortIncompleteMultipartDays"] == 1
    assert lifecycle["expirationRules"] == []
    assert "storageLifecycle" in schema["properties"]
    assert "app.ops_minio_lifecycle" in template
    assert "MINIO_LIFECYCLE_APPLY" in template
    assert "helm.sh/hook" in template
    assert "before-hook-creation,hook-succeeded" in template


def test_helm_production_overlays_have_secret_and_metrics_hooks():
    values = yaml.safe_load((ROOT / "deploy" / "helm" / "atp" / "values.yaml").read_text(encoding="utf-8"))
    secret = (ROOT / "deploy" / "helm" / "atp" / "templates" / "secret.yaml").read_text(encoding="utf-8")
    helpers = (ROOT / "deploy" / "helm" / "atp" / "templates" / "_helpers.tpl").read_text(encoding="utf-8")
    service_monitor = (ROOT / "deploy" / "helm" / "atp" / "templates" / "servicemonitor.yaml").read_text(
        encoding="utf-8"
    )
    performance_service = (
        ROOT / "deploy" / "helm" / "atp" / "templates" / "performance-worker-service.yaml"
    ).read_text(encoding="utf-8")
    ingress = (ROOT / "deploy" / "helm" / "atp" / "templates" / "ingress.yaml").read_text(encoding="utf-8")

    assert values["secret"] == {"create": True, "existingName": ""}
    assert secret.lstrip().startswith("{{- if .Values.secret.create }}")
    assert "if .Values.secret.create" in secret
    assert 'define "atp.secretName"' in helpers
    assert ".Values.secret.existingName" in helpers
    assert "monitoring.coreos.com/v1" in service_monitor
    assert ".Values.metrics.serviceMonitor.enabled" in service_monitor
    assert "path: /metrics" in service_monitor
    assert "performance-worker" in service_monitor
    assert "performance-worker" in performance_service
    assert "targetPort: metrics" in performance_service
    assert "gt (int .Values.performanceWorker.metricsPort) 0" in service_monitor
    assert "gt (int .Values.performanceWorker.metricsPort) 0" in performance_service
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
    assert ".Values.performanceWorker.autoIdentity" in content
    assert 'export PERFORMANCE_NODE_ID="${HOSTNAME}"' in content
    assert 'export PERFORMANCE_NODE_QUEUE="performance.${HOSTNAME}"' in content
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


def test_helm_chart_can_render_dedicated_web_recording_worker():
    content = (ROOT / "deploy" / "helm" / "atp" / "templates" / "web-recorder-deployment.yaml").read_text(
        encoding="utf-8"
    )
    schema = json.loads((ROOT / "deploy" / "helm" / "atp" / "values.schema.json").read_text(encoding="utf-8"))

    assert "{{- if .Values.webRecorder.enabled }}" in content
    assert "app.kubernetes.io/component: web-recorder" in content
    assert "python -m app.web_recording_worker" in content
    assert "Xvfb" in content
    assert 'printf "%s-$(POD_NAME)" .Values.webRecorder.workerId' in content
    assert "fieldPath: metadata.name" in content
    assert ".Values.webRecorder.maxSessions" in content
    assert ".Values.webRecorder.healthFile" in content
    assert "readinessProbe" in content
    assert "livenessProbe" in content
    assert "webRecorder" in schema["properties"]


def test_worker_dockerfile_bundles_k6_for_performance_queue():
    content = (ROOT / "backend" / "Dockerfile.worker").read_text(encoding="utf-8")

    assert "ARG GO_IMAGE=golang:1.26.6-bookworm@sha256:" in content
    assert "ARG K6_COMMIT=00a9a1b7f552d6bb4337278b10ae25aac0f4e666" in content
    assert "git clone --depth 1 --branch v2.2.0 https://github.com/grafana/k6.git ." in content
    assert 'test "$(git rev-parse HEAD)" = "${K6_COMMIT}"' in content
    assert 'CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /k6 .' in content
    assert "COPY --from=k6-build /k6 /usr/local/bin/k6" in content
    assert "RUN chmod 0755 /usr/local/bin/k6" in content
    assert "k6 version" in content
    assert "locust --version" in content
    assert "import grpc, grpc_tools" in content


def test_docker_compose_acceptance_stack_isolated_and_has_real_targets():
    compose = yaml.safe_load((ROOT / "docker-compose.performance-acceptance.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert compose["name"] == "atp-performance-acceptance"
    assert {
        "postgres",
        "redis",
        "minio",
        "backend",
        "worker",
        "web-recorder",
        "performance-worker",
        "acceptance-target",
    } <= services.keys()
    assert services["backend"]["ports"] == ["127.0.0.1:18080:8000"]
    assert services["backend"]["environment"]["WEB_RECORDER_MODE"] == "worker"
    assert (
        services["backend"]["environment"]["WEB_RECORDER_WORKER_QUEUE_PREFIX"]
        == "atp:web-recording:commands"
    )
    assert services["backend"]["healthcheck"]["test"][0] == "CMD"
    assert "/health" in " ".join(services["backend"]["healthcheck"]["test"])
    worker = services["worker"]
    assert worker["environment"]["CELERY_QUEUES"] == "default,maintenance"
    assert worker["environment"]["WORKER_METRICS_PORT"] == "9091"
    assert worker["environment"]["ADB_SCAN_ENABLED"] == "false"
    assert worker["environment"]["PERFORMANCE_NODE_ENABLED"] == "false"
    assert worker["depends_on"]["backend"]["condition"] == "service_healthy"
    worker_command = " ".join(worker["command"])
    assert "celery -A app.worker.celery_app worker" in worker_command
    assert '"$${CELERY_QUEUES}"' in worker_command
    assert services["performance-worker"]["environment"]["PERFORMANCE_NODE_ID"] == "worker-a"
    assert services["performance-worker"]["environment"]["PERFORMANCE_NODE_QUEUE"] == "performance.worker-a"
    assert services["performance-worker"]["environment"]["CELERY_QUEUES"] == "performance.worker-a"
    assert services["performance-worker"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert "grpc-target" in services["acceptance-target"]["networks"]["default"]["aliases"]
    assert "http-target" in services["acceptance-target"]["networks"]["default"]["aliases"]
    tls_command = " ".join(services["acceptance-tls"]["command"])
    assert "chown 10001:10001 /certs/server.crt /certs/server.key" in tls_command
    performance_command = " ".join(services["performance-worker"]["command"])
    assert 'queues="$${CELERY_QUEUES:-performance}"' in performance_command
    assert 'queues="$${queues},performance"' in performance_command
    assert "acceptance_tls:/etc/atp/tls:ro" in services["performance-worker"]["volumes"]
    recorder = services["web-recorder"]
    assert recorder["environment"]["WEB_RECORDER_MODE"] == "worker"
    assert recorder["environment"]["WEB_RECORDER_WORKER_QUEUE_PREFIX"] == "atp:web-recording:commands"
    assert recorder["environment"]["WEB_RECORDER_WORKER_ID"] == "web-recorder-q19-1"
    assert recorder["environment"]["WEB_RECORDER_HEALTH_FILE"] == "/tmp/atp-web-recorder.ready"
    recorder_command = " ".join(recorder["command"])
    assert "Xvfb" in recorder_command
    assert "python -m app.web_recording_worker" in recorder_command
    assert "rm -f \"/tmp/.X$${display_number}-lock\"" in recorder_command
    assert "export DISPLAY=\"$${display}\"" in recorder_command
    assert "xvfb_pid=$$!" in recorder_command
    assert recorder["healthcheck"]["test"][0] == "CMD"
    assert recorder["depends_on"]["backend"]["condition"] == "service_healthy"
    assert "./docs/evidence:/evidence" in services["acceptance-tools"]["volumes"]
    assert services["acceptance-tools"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert services["acceptance-tools"]["depends_on"]["web-recorder"]["condition"] == "service_healthy"
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
