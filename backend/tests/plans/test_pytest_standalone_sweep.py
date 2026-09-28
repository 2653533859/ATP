"""Keep concurrent standalone pytest runs isolated on Windows."""

import importlib.util
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]


def test_each_standalone_file_receives_a_unique_basetemp(monkeypatch):
    path = ROOT / "scripts" / "pytest-standalone-sweep.py"
    spec = importlib.util.spec_from_file_location("pytest_standalone_sweep", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    first = ROOT / "backend" / "tests" / "worker" / "test_celery_routing.py"
    second = ROOT / "backend" / "tests" / "worker" / "test_tasks_performance.py"

    assert module.run_one(first, timeout=5)[1] == 0
    assert module.run_one(second, timeout=5)[1] == 0
    basetemps = [Path(command[command.index("--basetemp") + 1]) for command in calls]
    assert basetemps[0] != basetemps[1]
    assert all(path.parent == ROOT / ".local-run" / "pytest-standalone" for path in basetemps)
