"""Contract tests for the local SMTP link check command.

这个脚本只做本地链路自检，不能被当成外部渠道验收证据；下面的断言用来锁死
“不会写出 passed 状态”“不接受命令行凭据”“只绑定回环地址”三条边界。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "notification-smtp-link-check.py"


def _module():
    spec = importlib.util.spec_from_file_location("notification_smtp_link_check", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_link_check_never_reports_a_passed_status():
    """报告状态只能是 local_link_only 或 failed，避免被误读为发布验收通过。"""

    source = SCRIPT.read_text(encoding="utf-8")
    assert 'status="local_link_only"' in source or '"local_link_only"' in source
    assert 'status="passed"' not in source
    assert '"passed_with_skips"' not in source


def test_link_check_declares_its_limited_scope():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "does not close the external SMTP/WeCom/DingTalk delivery gate" in source
    assert "smtp-local-sink" in source


def test_link_check_binds_loopback_only_and_takes_no_credential_arguments():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"127.0.0.1"' in source
    assert "0.0.0.0" not in source
    for flag in ("--password", "--token", "--secret", "--webhook"):
        assert flag not in source


def test_link_check_goes_through_the_production_send_entry_point():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "send_notification_channel" in source
    # 不允许绕过校验与重试策略直接调用私有 sender。
    assert "_send_email(" not in source


def test_link_check_uses_reserved_example_domains_only():
    module = _module()
    for recipient in module.RECIPIENTS:
        candidate = recipient.strip()
        if not candidate:
            continue
        assert candidate.endswith("example.com") or candidate.endswith("example.org>")
    assert module.EXPECTED_ENVELOPE == ["qa@example.com", "ops@example.org"]


def test_link_check_expects_all_six_performance_fields():
    module = _module()
    assert set(module.EXPECTED_FIELDS) == {
        "rps",
        "p95_ms",
        "p99_ms",
        "error_rate",
        "threshold_status",
        "performance_event_reasons",
    }


def test_link_check_report_excludes_credentials():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"credential_values_recorded": False' in source
    assert "SMTP_PASSWORD" in source  # 显式清空，而不是复用真实凭据
    assert 'settings.SMTP_PASSWORD = ""' in source
