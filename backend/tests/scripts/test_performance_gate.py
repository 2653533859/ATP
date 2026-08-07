import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "performance-gate.py"


def _module():
    spec = importlib.util.spec_from_file_location("performance_gate_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_exit_code_is_ci_stable():
    gate = _module().gate_exit_code

    assert gate({"status": "passed"}) == 0
    assert gate({"status": "failed"}) == 1
    assert gate({"status": "cancelled"}) == 1
    assert gate({"status": "not_configured"}) == 2
    assert gate({"status": "pending"}) == 3
