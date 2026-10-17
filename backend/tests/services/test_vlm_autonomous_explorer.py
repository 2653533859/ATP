"""多模态 VLM 屏幕理解与自主探索服务单测 (T2.1)"""

from __future__ import annotations

import pytest

from app.services.vlm_autonomous_explorer import (
    clear_exploration_sessions,
    decide_and_step_exploration,
    get_exploration_session,
    list_exploration_sessions,
    perceive_screen_elements,
    start_exploration_session,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_exploration_sessions()
    yield
    clear_exploration_sessions()


def test_perceive_elements_and_step_exploration():
    # 模拟屏幕截图
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    # 1. 元素感知
    elements = perceive_screen_elements(dummy_b64, platform="ios")
    assert len(elements) >= 3
    labels = [e.label for e in elements]
    assert any("登录" in l for l in labels)
    assert any("Apple Pay" in l for l in labels)

    # 2. 会话启动
    sess = start_exploration_session(
        platform="ios",
        device_id="00008101-IPHONE-REAL",
        goal="探索商城商品结账并测试支付流程",
        max_steps=10,
    )
    assert sess.platform == "ios"
    assert sess.status == "ACTIVE"
    assert sess.step_count == 0

    # 3. 推进第一步探索
    sess_step1, act1 = decide_and_step_exploration(sess.session_id, dummy_b64)
    assert sess_step1.step_count == 1
    assert "action_type" in act1
    assert len(sess_step1.states) == 1
    assert len(sess_step1.transitions) == 1

    # 4. 推进第二步探索
    sess_step2, act2 = decide_and_step_exploration(sess.session_id, dummy_b64)
    assert sess_step2.step_count == 2
    assert "action_type" in act2
    assert len(sess_step2.transitions) == 2

    # 查验单条会话与列表
    assert get_exploration_session(sess.session_id) is not None
    assert len(list_exploration_sessions()) == 1
