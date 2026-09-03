"""Validate repository-local deployment and disaster-recovery prerequisites."""

from __future__ import annotations

import argparse
import json
import os
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
    args = parser.parse_args()

    failures: list[str] = []
    skipped: list[str] = []
    _check_required_files(failures)
    _check_data_files(failures)
    strict = args.strict
    _check_shell_scripts(strict or args.require_shell, skipped, failures)
    _check_document_contracts(failures)
    _check_android_worker_profiles(failures)
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
