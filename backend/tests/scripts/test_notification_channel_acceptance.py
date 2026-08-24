"""Contract tests for the external notification acceptance command."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "notification-channel-acceptance.py"
NOTIFIER = ROOT / "backend" / "app" / "services" / "notifier.py"


def _notifier_module():
    # Some legacy notification route tests replace app.services.notifier in
    # sys.modules. Load the production module under a unique name so this
    # contract test remains valid when the entire suite runs together.
    spec = importlib.util.spec_from_file_location("notification_notifier_contract", NOTIFIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_acceptance_failure_path_uses_shared_secret_redaction():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "_safe_exception_message" in source
    assert 'str(exc).split("?", 1)[0]' not in source

    module = _notifier_module()
    safe = module._safe_exception_message(
        RuntimeError("provider rejected https://user:password@example.test/hook?access_token=raw-secret")
    )
    assert "raw-secret" not in safe
    assert "password" not in safe
    assert "<redacted>" in safe


def test_acceptance_report_never_records_credential_values():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"credential_values_recorded": False' in source
    assert "ATP_ACCEPTANCE_DINGTALK_SECRET" in source
    assert "os.environ.items" not in source
