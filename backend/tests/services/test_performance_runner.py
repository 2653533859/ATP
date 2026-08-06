import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import performance


def _fake_download(_object_name: str, local_path: Path) -> None:
    Path(local_path).write_text("export default function() {}", encoding="utf-8")


def test_run_k6_script_uploads_summary_on_success(monkeypatch):
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        result_path = Path(cmd[3])
        result_path.write_text(
            json.dumps(
                {
                    "metrics": {
                        "http_reqs": {"values": {"rate": 9.5}},
                        "http_req_duration": {"values": {"p(95)": 120, "p(99)": 180}},
                        "http_req_failed": {"values": {"rate": 0}},
                    }
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    def fake_upload(object_name, local_path, content_type):
        captured["upload"] = {
            "object_name": object_name,
            "exists": Path(local_path).exists(),
            "content_type": content_type,
        }
        return object_name

    monkeypatch.setattr(performance.minio_client, "download_file", _fake_download, raising=False)
    monkeypatch.setattr(performance.subprocess, "run", fake_run)
    monkeypatch.setattr(performance.minio_client, "upload_file", fake_upload, raising=False)

    summary, object_name, duration_ms = performance.run_k6_script(
        run_id=12,
        script_object_name="performance/scripts/demo.js",
        options={"env": {"TARGET_URL": "https://example.test"}, "vus": 2, "duration": "1s"},
        timeout_seconds=10,
    )

    assert captured["cmd"][0:3] == ["k6", "run", "--summary-export"]
    assert captured["cmd"][4].endswith("script.js")
    assert captured["env"]["TARGET_URL"] == "https://example.test"
    assert json.loads(captured["env"]["ATP_K6_OPTIONS"]) == {"duration": "1s", "vus": 2}
    assert summary["exit_code"] == 0
    assert summary["rps"] == 9.5
    assert object_name == "performance/runs/12/summary.json"
    assert captured["upload"] == {
        "object_name": "performance/runs/12/summary.json",
        "exists": True,
        "content_type": "application/json",
    }
    assert duration_ms >= 0


def test_run_k6_script_keeps_summary_when_k6_exits_nonzero(monkeypatch):
    def fake_run(cmd, **_kwargs):
        Path(cmd[3]).write_text(
            json.dumps({"metrics": {"http_req_failed": {"values": {"rate": 0.25}}}}),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=99, stdout="", stderr="threshold failed")

    monkeypatch.setattr(performance.minio_client, "download_file", _fake_download, raising=False)
    monkeypatch.setattr(performance.subprocess, "run", fake_run)
    monkeypatch.setattr(
        performance.minio_client, "upload_file", lambda object_name, *_a, **_kw: object_name, raising=False
    )

    summary, object_name, _duration_ms = performance.run_k6_script(
        run_id=13,
        script_object_name="performance/scripts/fail.js",
    )

    assert summary["exit_code"] == 99
    assert summary["error_rate"] == 0.25
    assert summary["k6_error"] == "threshold failed"
    assert object_name == "performance/runs/13/summary.json"


def test_run_k6_script_raises_when_summary_missing(monkeypatch):
    monkeypatch.setattr(performance.minio_client, "download_file", _fake_download, raising=False)
    monkeypatch.setattr(
        performance.subprocess,
        "run",
        lambda *_a, **_kw: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )

    with pytest.raises(RuntimeError, match="boom"):
        performance.run_k6_script(
            run_id=14,
            script_object_name="performance/scripts/missing.js",
        )
