import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import performance


def _fake_download(_object_name: str, local_path: Path) -> None:
    Path(local_path).write_text("export default function() {}", encoding="utf-8")


def _fake_process(returncode: int, stdout_text: str = "", stderr_text: str = "", **kwargs):
    for stream, content in ((kwargs.get("stdout"), stdout_text), (kwargs.get("stderr"), stderr_text)):
        if stream is not None and content:
            stream.write(content)
            stream.flush()
    return SimpleNamespace(
        returncode=returncode,
        poll=lambda: returncode,
        wait=lambda timeout=None: returncode,
    )


def test_run_k6_script_uploads_summary_on_success(monkeypatch):
    captured: dict = {}

    def fake_popen(cmd, **kwargs):
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
        return _fake_process(0, stdout_text="ok", **kwargs)

    def fake_upload(object_name, local_path, content_type):
        captured["upload"] = {
            "object_name": object_name,
            "exists": Path(local_path).exists(),
            "content_type": content_type,
        }
        return object_name

    monkeypatch.setattr(performance.minio_client, "download_file", _fake_download, raising=False)
    monkeypatch.setattr(performance.subprocess, "Popen", fake_popen)
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
    def fake_popen(cmd, **_kwargs):
        Path(cmd[3]).write_text(
            json.dumps({"metrics": {"http_req_failed": {"values": {"rate": 0.25}}}}),
            encoding="utf-8",
        )
        return _fake_process(99, stderr_text="threshold failed", **_kwargs)

    monkeypatch.setattr(performance.minio_client, "download_file", _fake_download, raising=False)
    monkeypatch.setattr(performance.subprocess, "Popen", fake_popen)
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
        "Popen",
        lambda *_a, **_kw: _fake_process(1, stderr_text="boom", **_kw),
    )

    with pytest.raises(RuntimeError, match="boom"):
        performance.run_k6_script(
            run_id=14,
            script_object_name="performance/scripts/missing.js",
        )


def test_run_k6_script_terminates_process_when_cancelled(monkeypatch):
    class _RunningProcess:
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 1

        def wait(self, timeout=None):
            return self.returncode

        def communicate(self):
            return "", "cancelled"

    process = _RunningProcess()
    monkeypatch.setattr(performance.minio_client, "download_file", _fake_download, raising=False)
    monkeypatch.setattr(performance.subprocess, "Popen", lambda *_a, **_kw: process)

    with pytest.raises(performance.PerformanceRunCancelled):
        performance.run_k6_script(
            run_id=15,
            script_object_name="performance/scripts/cancel.js",
            cancel_check=lambda: True,
        )

    assert process.returncode == 1


def test_run_k6_script_invokes_metric_callback_while_process_is_running(monkeypatch):
    class _ShortRunningProcess:
        returncode = 0

        def __init__(self):
            self.poll_count = 0

        def poll(self):
            self.poll_count += 1
            return None if self.poll_count == 1 else self.returncode

        def wait(self, timeout=None):
            return self.returncode

    process = _ShortRunningProcess()

    def fake_popen(cmd, **_kwargs):
        Path(cmd[3]).write_text(json.dumps({"metrics": {}}), encoding="utf-8")
        return process

    monkeypatch.setattr(performance.minio_client, "download_file", _fake_download, raising=False)
    monkeypatch.setattr(performance.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        performance.minio_client,
        "upload_file",
        lambda object_name, *_a, **_kw: object_name,
        raising=False,
    )
    samples: list[int] = []

    performance.run_k6_script(
        run_id=16,
        script_object_name="performance/scripts/sample.js",
        metric_callback=lambda: samples.append(1),
        metric_interval_seconds=0,
    )

    assert samples == [1]
