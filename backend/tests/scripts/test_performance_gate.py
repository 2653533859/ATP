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


def test_default_idempotency_key_reuses_ci_run_identity(monkeypatch):
    script = _module()
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")

    assert script.default_idempotency_key(7, 2) == "ci-12345-performance-7-env-2"


def test_default_idempotency_key_is_unique_for_local_cli(monkeypatch):
    script = _module()
    monkeypatch.delenv("CI_PIPELINE_ID", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("BUILD_BUILDID", raising=False)
    monkeypatch.delenv("BUILD_ID", raising=False)

    first = script.default_idempotency_key(7, None)
    second = script.default_idempotency_key(7, None)

    assert first.startswith("cli-performance-7-")
    assert first != second


def test_build_gate_url_only_adds_opt_in_baseline_policies():
    script = _module()

    assert script.build_gate_url("https://atp.example/", 9) == (
        "https://atp.example/api/v1/webhook/performance-runs/9/gate"
    )
    assert script.build_gate_url(
        "https://atp.example",
        9,
        require_baseline=True,
        fail_on_baseline_regression=True,
    ) == (
        "https://atp.example/api/v1/webhook/performance-runs/9/gate?"
        "require_baseline=true&fail_on_baseline_regression=true"
    )
