from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import performance_jmeter
from app.services.performance_jmeter import parse_jmeter_jtl
from app.services.performance_jmeter import resolve_jmeter_executable


def test_resolve_jmeter_executable_supports_windows_batch_and_unix_binary(monkeypatch):
    available = {"jmeter.bat": r"C:\JMeter\bin\jmeter.bat", "jmeter": "/usr/bin/jmeter"}
    monkeypatch.setattr(performance_jmeter.shutil, "which", lambda name: available.get(name))

    assert resolve_jmeter_executable(windows=True) == available["jmeter.bat"]
    assert resolve_jmeter_executable(windows=False) == available["jmeter"]


def test_resolve_jmeter_executable_returns_platform_default_when_not_on_path(monkeypatch):
    monkeypatch.setattr(performance_jmeter.shutil, "which", lambda _name: None)

    assert resolve_jmeter_executable(windows=True) == "jmeter.bat"
    assert resolve_jmeter_executable(windows=False) == "jmeter"


def test_parse_jmeter_jtl_returns_common_summary_and_thresholds(tmp_path: Path):
    path = tmp_path / "result.jtl"
    path.write_text(
        "timeStamp,elapsed,label,responseCode,success,bytes,sentBytes\n"
        "1000,100,health,200,true,120,20\n"
        "2000,300,health,500,false,80,25\n"
        "3000,200,health,200,true,100,22\n",
        encoding="utf-8",
    )

    result = parse_jmeter_jtl(path, {"error_rate": ["<= 0.5"]})

    assert result["executor"] == "jmeter"
    assert result["iterations"] == 3
    assert result["error_rate"] == 1 / 3
    assert result["rps"] == 1.5
    assert result["data_received"] == 300
    assert result["thresholds"]["error_rate"]["<= 0.5"]["ok"] is True


def test_jmeter_parsing_handles_empty_values_single_sample_and_invalid_rules(tmp_path: Path):
    path = tmp_path / "empty-values.jtl"
    path.write_text(
        "timeStamp,elapsed,label,responseCode,success,bytes,sentBytes\n"
        "1000,100,health,200,true,,bad\n"
        "2000,,health,200,0,20,10\n",
        encoding="utf-8",
    )

    result = parse_jmeter_jtl(
        path,
        {
            "iterations": [">= 1", "not-a-rule"],
            "rps": "<= 0",
            "missing": "<= 1",
            "invalid": {"bad": True},
        },
    )

    assert result["p95_ms"] == 100.0
    assert result["rps"] == 2.0
    assert result["error_rate"] == 0.5
    assert result["data_received"] == 20
    assert result["data_sent"] == 10
    assert result["thresholds"]["iterations"][">= 1"]["ok"] is True
    assert "missing" not in result["thresholds"]


def test_run_jmeter_script_uploads_summary_and_nonzero_error(monkeypatch):
    uploaded = []

    def download(_object_name, path):
        Path(path).write_text("<jmeterTestPlan />", encoding="utf-8")

    def run_process(command, **kwargs):
        jtl_path = Path(kwargs["cwd"]) / "result.jtl"
        jtl_path.write_text(
            "timeStamp,elapsed,label,responseCode,success,bytes,sentBytes\n" "1000,10,health,500,false,2,1\n",
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=2, stderr="failed", stdout=""), 12

    monkeypatch.setattr(performance_jmeter.minio_client, "download_file", download)
    monkeypatch.setattr(performance_jmeter, "run_performance_process", run_process)
    monkeypatch.setattr(
        performance_jmeter.minio_client,
        "upload_file",
        lambda name, path, content_type: uploaded.append((name, Path(path).read_text(encoding="utf-8"), content_type)),
    )

    summary, object_name, duration = performance_jmeter.run_jmeter_script(
        run_id=7,
        script_object_name="performance/scripts/test.jmx",
        options={"env": {"TARGET": "https://example.com"}},
    )

    assert duration == 12
    assert object_name == "performance/runs/7/summary.json"
    assert summary["exit_code"] == 2
    assert summary["jmeter_error"] == "failed"
    assert uploaded[-1][0] == object_name


def test_run_jmeter_script_archives_successful_html_report(monkeypatch):
    uploaded = []

    monkeypatch.setattr(
        performance_jmeter.minio_client,
        "download_file",
        lambda _name, path: Path(path).write_text("<jmeterTestPlan />", encoding="utf-8"),
    )

    def run_process(_command, **kwargs):
        Path(kwargs["cwd"], "result.jtl").write_text(
            "timeStamp,elapsed,label,responseCode,success,bytes,sentBytes\n" "1000,10,health,200,true,2,1\n",
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stderr="", stdout=""), 5

    def run_html(_command, **kwargs):
        output_dir = Path(kwargs["cwd"]) / "html-report"
        output_dir.mkdir(exist_ok=True)
        (output_dir / "index.html").write_text("<html />", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(performance_jmeter, "run_performance_process", run_process)
    monkeypatch.setattr(performance_jmeter.subprocess, "run", run_html)
    monkeypatch.setattr(
        performance_jmeter.minio_client,
        "upload_file",
        lambda name, _path, content_type: uploaded.append((name, content_type)),
    )

    summary, _object_name, _duration = performance_jmeter.run_jmeter_script(
        run_id=8,
        script_object_name="performance/scripts/test.jmx",
        options={"html_report": True},
    )

    assert summary["html_report_object_name"] == "performance/runs/8/jmeter-html-report.zip"
    assert ("performance/runs/8/jmeter-html-report.zip", "application/zip") in uploaded
