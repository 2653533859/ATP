"""自主探索高危动作防护看门狗单测 (T4.1)"""

from __future__ import annotations

import pytest

from app.services.autonomous_exploration_safety_guard import (
    RiskCategory,
    RiskSeverity,
    SafetyVerdict,
    clear_safety_violations,
    evaluate_action_safety,
    list_safety_violations,
)
from app.services.vlm_autonomous_explorer import (
    DetectedUIElement,
    decide_and_step_exploration,
    start_exploration_session,
)


@pytest.fixture(autouse=True)
def clean_violations():
    clear_safety_violations()
    yield
    clear_safety_violations()


def test_safe_action_allowed():
    verdict, violation = evaluate_action_safety(
        session_id="sess_01",
        action_type="TAP",
        target_element_label="立即加入购物车",
        input_text=None,
    )
    assert verdict == SafetyVerdict.ALLOW
    assert violation is None
    assert len(list_safety_violations()) == 0


def test_block_account_destruction():
    verdict, violation = evaluate_action_safety(
        session_id="sess_02",
        action_type="TAP",
        target_element_label="永久注销账号并清空资产",
    )
    assert verdict == SafetyVerdict.BLOCK
    assert violation is not None
    assert violation.category == RiskCategory.ACCOUNT_DESTRUCTION
    assert violation.severity == RiskSeverity.CRITICAL
    assert "注销账号" in violation.triggered_keyword
    assert len(list_safety_violations(session_id="sess_02")) == 1


def test_block_factory_reset_system_purge():
    verdict, violation = evaluate_action_safety(
        session_id="sess_03",
        action_type="TAP",
        target_element_label="抹掉所有内容和设置 (恢复出厂设置)",
    )
    assert verdict == SafetyVerdict.BLOCK
    assert violation is not None
    assert violation.category == RiskCategory.SYSTEM_PURGE
    assert violation.severity == RiskSeverity.CRITICAL


def test_block_database_destruction_input():
    verdict, violation = evaluate_action_safety(
        session_id="sess_04",
        action_type="INPUT",
        target_element_label="SQL Console",
        input_text="DROP DATABASE atp_production;",
    )
    assert verdict == SafetyVerdict.BLOCK
    assert violation is not None
    assert violation.category == RiskCategory.DATABASE_DESTRUCTION


def test_safety_guard_circuit_breaker_integration():
    # 模拟探索时遭遇高危控件并触发自动熔断保护
    sess = start_exploration_session(platform="web", device_id="chrome_sandbox_01")

    # 创建包含高危注销按钮的假冒截图
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    # 我们通过 mock perceive_screen_elements 返回高危操作控件
    from unittest.mock import patch

    dangerous_elements = [
        DetectedUIElement("el_danger_1", "button", "注销会员账号", [10, 10, 100, 40]),
    ]

    with patch("app.services.vlm_autonomous_explorer.perceive_screen_elements", return_value=dangerous_elements):
        updated_sess, decided_action = decide_and_step_exploration(sess.session_id, dummy_b64)

        # 查验证明看门狗熔断拦截生效
        assert updated_sess.status == "CIRCUIT_BROKEN"
        assert decided_action.get("blocked") is True
        assert "看门狗拦截" in decided_action.get("reason", "")
        assert decided_action.get("violation_id") is not None
