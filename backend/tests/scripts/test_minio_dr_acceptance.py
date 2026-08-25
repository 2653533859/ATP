"""Contract tests for the cross-endpoint MinIO recovery acceptance command."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_script():
    path = ROOT / "scripts" / "minio-dr-acceptance.py"
    spec = importlib.util.spec_from_file_location("minio_dr_acceptance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_endpoint_and_lifecycle_requirement_validation():
    smoke = _load_script()

    assert smoke.parse_endpoint("minio.example.test:9000") == "minio.example.test:9000"
    assert smoke.endpoint_host("MINIO.EXAMPLE.TEST:9443") == "minio.example.test"
    assert smoke.parse_lifecycle_requirement("tmp/=7") == ("tmp/", 7)
    assert smoke._lifecycle_requirement_satisfied(
        [
            {
                "status": "Enabled",
                "prefix": "tmp/",
                "expiration_days": 7,
            }
        ],
        "tmp/",
        7,
    )

    with pytest.raises(smoke.AcceptanceError):
        smoke.parse_endpoint("https://user:secret@minio.example.test:9000/path")
    with pytest.raises(smoke.AcceptanceError):
        smoke.parse_lifecycle_requirement("/tmp/=7")


def test_endpoint_independence_rejects_loopback_aliases_and_same_ip(monkeypatch):
    smoke = _load_script()

    assert smoke.endpoints_share_host("localhost:9000", "127.0.0.1:9001") is True
    assert smoke.endpoints_share_host("[::1]:9000", "localhost:9001") is True

    def fake_getaddrinfo(host, *_args, **_kwargs):
        address = "192.0.2.10" if host in {"source.example.test", "backup.example.test"} else "192.0.2.11"
        return [(None, None, None, None, (address, 0))]

    monkeypatch.setattr(smoke.socket, "getaddrinfo", fake_getaddrinfo)
    assert smoke.endpoints_share_host("source.example.test:9000", "backup.example.test:9000") is True
    assert smoke.endpoints_share_host("source.example.test:9000", "other.example.test:9000") is False


def test_main_rejects_same_host_alias_before_connecting_to_minio(monkeypatch, tmp_path):
    smoke = _load_script()
    for prefix, endpoint, access_key, secret_key, bucket in (
        ("SOURCE", "localhost:9000", "source-user", "source-value", "atp"),
        ("TARGET", "127.0.0.1:9001", "target-user", "target-value", "atp-dr"),
    ):
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_ENDPOINT", endpoint)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_ACCESS_KEY", access_key)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_SECRET_KEY", secret_key)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_BUCKET", bucket)

    class _UnexpectedClient:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("same-host validation must run before MinIO connection")

    monkeypatch.setattr(smoke, "Minio", _UnexpectedClient)
    report_path = tmp_path / "same-host.json"

    assert smoke.main(["--report", str(report_path)]) == 1
    evidence = json.loads(report_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "failed"
    assert any(item["name"] == "endpoint-independence" and item["status"] == "FAIL" for item in evidence["checks"])


def test_main_copies_restores_and_cleans_objects_across_endpoints(monkeypatch, tmp_path):
    smoke = _load_script()

    for prefix, endpoint, access_key, secret_key, bucket in (
        ("SOURCE", "primary.example.test:9000", "source-user", "source-secret", "atp"),
        ("TARGET", "backup.example.test:9000", "target-user", "target-secret", "atp-dr"),
    ):
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_ENDPOINT", endpoint)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_ACCESS_KEY", access_key)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_SECRET_KEY", secret_key)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_BUCKET", bucket)

    class _Response:
        def __init__(self, payload: bytes):
            self.payload = payload

        def read(self):
            return self.payload

        def close(self):
            return None

        def release_conn(self):
            return None

    class _Client:
        storage: dict[tuple[str, str], bytes] = {}

        def __init__(self, endpoint, access_key, secret_key, *, secure):
            assert access_key.endswith("-user")
            assert secret_key.endswith("-secret")
            self.endpoint = endpoint
            self.secure = secure

        def bucket_exists(self, _bucket):
            return True

        def get_bucket_lifecycle(self, _bucket):
            return None

        def put_object(self, bucket, object_name, stream, length, *, content_type):
            assert content_type == "application/json"
            payload = stream.read()
            assert len(payload) == length
            self.storage[(self.endpoint, f"{bucket}/{object_name}")] = payload

        def get_object(self, bucket, object_name):
            return _Response(self.storage[(self.endpoint, f"{bucket}/{object_name}")])

        def remove_object(self, bucket, object_name):
            self.storage.pop((self.endpoint, f"{bucket}/{object_name}"), None)

        def list_objects(self, bucket, *, prefix, recursive):
            assert recursive is True
            prefix_key = f"{bucket}/{prefix}"
            for key in self.storage:
                if key[0] == self.endpoint and key[1].startswith(prefix_key):
                    yield SimpleNamespace(object_name=key[1][len(f"{bucket}/") :])

    monkeypatch.setattr(smoke, "Minio", _Client)
    report_path = tmp_path / "minio-dr.json"

    assert smoke.main(["--report", str(report_path)]) == 0

    evidence = json.loads(report_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "passed"
    assert {item["name"] for item in evidence["checks"]} >= {
        "source-bucket",
        "target-bucket",
        "source-lifecycle-audit",
        "target-lifecycle-audit",
        "source-round-trip",
        "cross-endpoint-copy",
        "cross-endpoint-restore",
        "cleanup",
    }
    content = report_path.read_text(encoding="utf-8")
    assert "source-secret" not in content
    assert "target-secret" not in content
    assert _Client.storage == {}


def test_main_writes_redacted_failure_evidence_for_unexpected_minio_errors(monkeypatch, tmp_path):
    smoke = _load_script()
    for prefix, endpoint, access_key, secret_key, bucket in (
        ("SOURCE", "primary.example.test:9000", "source-user", "source-secret", "atp"),
        ("TARGET", "backup.example.test:9000", "target-user", "target-secret", "atp-dr"),
    ):
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_ENDPOINT", endpoint)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_ACCESS_KEY", access_key)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_SECRET_KEY", secret_key)
        monkeypatch.setenv(f"ATP_MINIO_DR_{prefix}_BUCKET", bucket)

    class _FailingClient:
        def __init__(self, _endpoint, _access_key, secret_key, *, secure):
            del secure
            self.secret_key = secret_key

        def bucket_exists(self, _bucket):
            raise RuntimeError(f"transport failed for {self.secret_key}")

    monkeypatch.setattr(smoke, "Minio", _FailingClient)
    report_path = tmp_path / "minio-dr-failed.json"

    assert smoke.main(["--report", str(report_path)]) == 1

    content = report_path.read_text(encoding="utf-8")
    evidence = json.loads(content)
    assert evidence["status"] == "failed"
    assert "acceptance-execution" in {item["name"] for item in evidence["checks"]}
    assert "source-secret" not in content
    assert "target-secret" not in content
