"""Contract tests for the Android Backend/Windows Agent configuration pair check."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "validate-android-worker-config.py"


def _module():
    spec = importlib.util.spec_from_file_location("validate_android_worker_config", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _pair():
    module = _module()
    shared = {
        "POSTGRES_HOST": "db.internal",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "atp",
        "POSTGRES_USER": "atp",
        "POSTGRES_PASSWORD": "same-password",
        "REDIS_HOST": "redis.internal",
        "REDIS_PORT": "6379",
        "REDIS_PASSWORD": "same-redis-password",
        "MINIO_HOST": "minio.internal",
        "MINIO_PORT": "9000",
        "MINIO_ROOT_USER": "minio",
        "MINIO_ROOT_PASSWORD": "same-minio-password",
        "MINIO_BUCKET": "atp",
        "APP_SECRET_KEY": "same-app-secret",
        "ENCRYPTION_KEY": "same-encryption-key",
    }
    backend = {
        **shared,
        "ADB_SCAN_MODE": "worker",
        "ADB_SCAN_ENABLED": "true",
        "CELERY_QUEUES": "default,ios,ai,maintenance,performance",
        "ANDROID_WORKER_QUEUE": "mobile_special",
        "ANDROID_WORKER_REGISTRY_PREFIX": "atp:android-worker",
    }
    agent = {
        **shared,
        "ADB_SCAN_MODE": "local",
        "ADB_SCAN_ENABLED": "true",
        "CELERY_QUEUES": "android,mobile_special",
        "ANDROID_WORKER_QUEUE": "mobile_special",
        "ANDROID_WORKER_REGISTRY_PREFIX": "atp:android-worker",
    }
    return module, backend, agent


def _failed(checks):
    return {item.name for item in checks if not item.passed}


def test_matching_backend_and_agent_profiles_pass_without_exposing_values(capsys):
    module, backend, agent = _pair()

    checks = module.validate_profiles(backend, agent)
    assert not _failed(checks)

    report = module._report(checks, Path("backend.env"), Path("agent.env"))
    assert report["status"] == "passed"
    assert report["credential_values_recorded"] is False
    assert "same-password" not in str(report)
    assert "same-encryption-key" not in capsys.readouterr().out


@pytest.mark.parametrize("key", ["REDIS_HOST", "REDIS_PORT", "MINIO_BUCKET", "APP_SECRET_KEY", "ENCRYPTION_KEY"])
def test_shared_infrastructure_or_secret_mismatch_is_rejected(key):
    module, backend, agent = _pair()
    agent[key] = "different-value"

    assert f"shared {key}" in _failed(module.validate_profiles(backend, agent))


def test_queue_and_scan_mode_mismatch_is_rejected():
    module, backend, agent = _pair()
    backend["ADB_SCAN_MODE"] = "local"
    backend["CELERY_QUEUES"] = "default,android"
    agent["CELERY_QUEUES"] = "android,mobile_special,default"

    failed = _failed(module.validate_profiles(backend, agent))
    assert {"backend ADB scan mode", "backend Android queues excluded", "agent queue set"} <= failed


def test_env_reader_supports_export_and_quoted_values(tmp_path):
    module = _module()
    path = tmp_path / "sample.env"
    path.write_text("export REDIS_HOST='redis.internal'\n# comment\nREDIS_PORT=6379\n", encoding="utf-8")

    assert module.read_env(path) == {"REDIS_HOST": "redis.internal", "REDIS_PORT": "6379"}


def test_env_reader_rejects_malformed_assignment(tmp_path):
    module = _module()
    path = tmp_path / "sample.env"
    path.write_text("not-an-assignment\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected KEY=value"):
        module.read_env(path)
