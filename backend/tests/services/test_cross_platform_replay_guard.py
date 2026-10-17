"""跨端迁移回放安全防护看门狗单测 (T4.1)"""

from __future__ import annotations

import pytest

from app.services.cross_platform_replay_guard import (
    ReplayGuardVerdict,
    ReplayViolationType,
    ScreenViewport,
    clear_replay_violations,
    evaluate_replay_step_safety,
    list_replay_violations,
)


@pytest.fixture(autouse=True)
def clean_violations():
    clear_replay_violations()
    yield
    clear_replay_violations()


def test_safe_step_allowed():
    verdict, violation = evaluate_replay_step_safety(
        migration_id="mig_001",
        step_id="s1",
        target_platform="android",
        action_type="TAP",
        element_label="立即加入购物车",
        coordinates=[150, 600],
        confidence=0.95,
    )
    assert verdict == ReplayGuardVerdict.ALLOW
    assert violation is None
    assert len(list_replay_violations()) == 0


def test_destructive_keyword_blocked():
    verdict, violation = evaluate_replay_step_safety(
        migration_id="mig_002",
        step_id="s2",
        target_platform="android",
        action_type="TAP",
        element_label="永久注销账号与会员资产",
        coordinates=[150, 600],
        confidence=0.95,
    )
    assert verdict == ReplayGuardVerdict.BLOCK
    assert violation is not None
    assert violation.violation_type == ReplayViolationType.HIGH_RISK_GESTURE
    assert "高危破坏词" in violation.reason
    assert len(list_replay_violations(migration_id="mig_002")) == 1


def test_coordinates_out_of_bounds_blocked():
    vp = ScreenViewport(width=1080, height=2400)

    # 1. 超出屏幕右边界
    verdict1, viol1 = evaluate_replay_step_safety(
        migration_id="mig_003",
        step_id="s3",
        target_platform="android",
        action_type="TAP",
        coordinates=[1200, 500],
        viewport=vp,
    )
    assert verdict1 == ReplayGuardVerdict.BLOCK
    assert viol1 is not None
    assert viol1.violation_type == ReplayViolationType.COORDINATE_OUT_OF_BOUNDS

    # 2. 超出极顶状态栏 (y < 10)
    verdict2, viol2 = evaluate_replay_step_safety(
        migration_id="mig_003",
        step_id="s4",
        target_platform="android",
        action_type="TAP",
        coordinates=[200, 5],
        viewport=vp,
    )
    assert verdict2 == ReplayGuardVerdict.BLOCK
    assert viol2 is not None
    assert viol2.violation_type == ReplayViolationType.COORDINATE_OUT_OF_BOUNDS


def test_low_confidence_gate_blocked_for_interactive_actions():
    verdict_tap, viol_tap = evaluate_replay_step_safety(
        migration_id="mig_004",
        step_id="s5",
        target_platform="ios",
        action_type="TAP",
        element_label="模糊按钮",
        confidence=0.35,  # 低于 0.50 阈值
    )
    assert verdict_tap == ReplayGuardVerdict.BLOCK
    assert viol_tap is not None
    assert viol_tap.violation_type == ReplayViolationType.LOW_CONFIDENCE_GATE

    # 验证非交互式步骤 (如 WAIT_DELAY / ASSERT) 放行
    verdict_wait, viol_wait = evaluate_replay_step_safety(
        migration_id="mig_004",
        step_id="s6",
        target_platform="ios",
        action_type="WAIT_DELAY",
        confidence=0.30,
    )
    assert verdict_wait == ReplayGuardVerdict.ALLOW
    assert viol_wait is None
