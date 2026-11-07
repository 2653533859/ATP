import importlib.util
from pathlib import Path
import sqlite3
import subprocess
from types import SimpleNamespace

import pytest


@pytest.fixture
def probe():
    path = Path(__file__).resolve().parents[3] / "scripts" / "android-agent-preflight.py"
    spec = importlib.util.spec_from_file_location("android_agent_preflight", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_does_not_execute_device_actions_or_report_serials(probe, monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="List of devices attached\nprivate-serial device product:test\n")

    monkeypatch.setattr(probe.subprocess, "run", run)
    report = probe.inspect_environment("adb", None)
    assert calls == [["adb", "devices", "-l"]]
    assert report["checks"]["adb"]["online"] == 1
    assert "private-serial" not in str(report)
    assert report["m0_accepted"] is False


def test_configured_model_is_not_claimed_as_model_verification(probe, monkeypatch, tmp_path):
    db = tmp_path / "probe.db"
    with sqlite3.connect(db) as conn:
        conn.execute("create table ai_llm_configs(enabled integer, supports_vision integer, api_key text)")
        conn.execute("insert into ai_llm_configs values (1,1,'must-not-be-read')")
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=""))
    report = probe.inspect_environment("adb", db)
    assert report["checks"]["model_config"]["enabled_vision_models"] == 1
    assert report["checks"]["model_config"]["model_call_verified"] is False
    assert "must-not-be-read" not in str(report)


def test_wrong_database_path_is_not_created(probe, monkeypatch, tmp_path):
    db = tmp_path / "missing.db"
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=""))
    report = probe.inspect_environment("adb", db)
    assert report["checks"]["model_config"]["status"] == "blocked"
    assert not db.exists()


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("adb", 15)])
def test_adb_unavailable_is_a_bounded_blocker(probe, monkeypatch, error):
    def run(*args, **kwargs):
        raise error

    monkeypatch.setattr(probe.subprocess, "run", run)
    assert probe.inspect_environment("adb", None)["checks"]["adb"]["reason"] == "adb_unavailable"
