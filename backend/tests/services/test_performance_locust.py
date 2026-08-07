from pathlib import Path
from types import SimpleNamespace

from app.services import performance_locust


def _write_script(_object_name: str, local_path: Path) -> None:
    local_path.write_text("from locust import HttpUser\n", encoding="utf-8")


def test_parse_locust_stats_uses_aggregate_row_and_evaluates_thresholds(tmp_path):
    stats = tmp_path / "stats.csv"
    stats.write_text(
        "Type,Name,Request Count,Failure Count,Requests/s,95%,99%\n"
        "GET,/health,90,2,3.0,120,220\n"
        "Aggregated,,100,5,3.3,150,250\n",
        encoding="utf-8",
    )

    result = performance_locust.parse_locust_stats(
        stats,
        {"p95_ms": ["<200"], "error_rate": ["<0.1"], "rps": [">4"]},
    )

    assert result["executor"] == "locust"
    assert result["rps"] == 3.3
    assert result["p95_ms"] == 150
    assert result["p99_ms"] == 250
    assert result["iterations"] == 100
    assert result["error_rate"] == 0.05
    assert result["thresholds"] == {
        "p95_ms": {"<200": {"ok": True}},
        "error_rate": {"<0.1": {"ok": True}},
        "rps": {">4": {"ok": False}},
    }


def test_run_locust_script_builds_headless_command_and_uploads_summary(monkeypatch):
    captured: dict = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        csv_prefix = Path(command[command.index("--csv") + 1])
        Path(f"{csv_prefix}_stats.csv").write_text(
            "Type,Name,Request Count,Failure Count,Requests/s,95%,99%\n" "Aggregated,,12,0,4.0,80,120\n",
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, poll=lambda: 0, wait=lambda timeout=None: 0)

    monkeypatch.setattr(performance_locust.minio_client, "download_file", _write_script, raising=False)
    monkeypatch.setattr(performance_locust.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        performance_locust.minio_client,
        "upload_file",
        lambda object_name, path, content_type: captured.update(
            upload=(object_name, Path(path).exists(), content_type)
        ),
        raising=False,
    )

    summary, object_name, duration_ms = performance_locust.run_locust_script(
        run_id=9,
        script_object_name="performance/scripts/locust.py",
        options={
            "users": 8,
            "spawn_rate": 2,
            "run_time": "15s",
            "host": "https://example.test",
            "env": {"TARGET_URL": "https://example.test"},
        },
    )

    assert captured["command"][:7] == [
        "locust",
        "-f",
        captured["command"][2],
        "--headless",
        "--only-summary",
        "--csv",
        captured["command"][6],
    ]
    assert "-u" in captured["command"] and "8" in captured["command"]
    assert "--host" in captured["command"] and "https://example.test" in captured["command"]
    assert summary["executor"] == "locust"
    assert summary["rps"] == 4
    assert object_name == "performance/runs/9/summary.json"
    assert captured["upload"] == (object_name, True, "application/json")
    assert duration_ms >= 0
