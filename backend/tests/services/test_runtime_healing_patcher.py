"""运行时失败拦截与自愈补丁应用器单测 (T1.2)"""

from __future__ import annotations

import pytest

from app.services.dynamic_locator_self_healer import (
    BrokenLocatorContext,
    CandidateDOMNode,
)
from app.services.runtime_healing_patcher import (
    PatchStatus,
    RuntimeHealingExecutionResult,
    RuntimeHealingVerdict,
    clear_healing_patches,
    commit_healing_patch,
    get_healing_patch,
    intercept_and_heal_step,
    list_healing_patches,
    reject_healing_patch,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_healing_patches()
    yield
    clear_healing_patches()


def test_intercept_and_heal_step_success():
    context = BrokenLocatorContext(
        step_id="step_click_cart",
        failed_locator_type="css",
        failed_locator_value="#btn-add-cart-legacy",
        element_text_hint="立即加购",
        element_role_hint="button",
    )

    screen_nodes = [
        CandidateDOMNode(
            node_id="node_cart_rebuilt",
            tag_name="button",
            text="立即加购",
            attributes={"data-action": "add-cart", "class": "btn-action"},
        ),
    ]

    res = intercept_and_heal_step(context, screen_nodes, case_id="case_shop_01", platform="web")
    assert isinstance(res, RuntimeHealingExecutionResult)
    assert res.verdict == RuntimeHealingVerdict.HEALED_AND_RESUMED
    assert res.patch is not None

    patch = res.patch
    assert patch.status == PatchStatus.APPLIED_IN_FLIGHT
    assert patch.broken_locator["value"] == "#btn-add-cart-legacy"
    assert "data-action='add-cart'" in patch.healed_locator["value"]
    assert patch.confidence_score >= 0.90

    # 再次遭遇同一失败步骤时，命中缓存补丁快速放行
    res_cached = intercept_and_heal_step(context, screen_nodes, case_id="case_shop_01", platform="web")
    assert res_cached.verdict == RuntimeHealingVerdict.HEALED_AND_RESUMED
    assert "命中历史自愈补丁" in res_cached.message


def test_intercept_and_heal_step_failure():
    context = BrokenLocatorContext(
        step_id="step_ghost",
        failed_locator_type="id",
        failed_locator_value="btn_ghost",
        element_text_hint="根本不存在的业务按钮",
    )

    res = intercept_and_heal_step(context, [], confidence_threshold=0.75)
    assert res.verdict == RuntimeHealingVerdict.HEALING_FAILED
    assert res.patch is None
    assert "自愈终止" in res.message


def test_commit_and_reject_patch_lifecycle():
    context = BrokenLocatorContext(
        step_id="step_login_btn",
        failed_locator_type="id",
        failed_locator_value="btn_login_old",
        element_text_hint="登录",
        element_role_hint="button",
    )
    nodes = [CandidateDOMNode("n_login", "button", text="登录", attributes={"id": "btn_login_new"})]

    res = intercept_and_heal_step(context, nodes)
    assert res.patch is not None
    patch_id = res.patch.patch_id

    # 1. 采纳永久生效
    ok_commit = commit_healing_patch(patch_id)
    assert ok_commit is True
    p_committed = get_healing_patch(patch_id)
    assert p_committed is not None
    assert p_committed.status == PatchStatus.COMMITTED_PERMANENT
    assert p_committed.committed_at is not None

    # 2. 状态检索
    committed_list = list_healing_patches(status="COMMITTED_PERMANENT")
    assert len(committed_list) == 1
    assert committed_list[0]["patch_id"] == patch_id

    # 3. 否决回滚
    ok_reject = reject_healing_patch(patch_id)
    assert ok_reject is True
    p_rejected = get_healing_patch(patch_id)
    assert p_rejected is not None
    assert p_rejected.status == PatchStatus.REJECTED
