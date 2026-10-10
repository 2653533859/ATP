import asyncio
from app.services.runtime_locator_healer import (
    RuntimeLocatorHealer,
    generate_candidate_selectors,
    is_locator_failure,
)


def test_is_locator_failure_detection():
    # Valid locator failure messages
    assert is_locator_failure("waiting for locator('#btn') failed: timeout 5000ms exceeded")
    assert is_locator_failure("元素不可见: #submit")
    assert is_locator_failure("页面中未找到文本: 确认登录")
    assert is_locator_failure("waiting for element to be visible: [data-testid='login']")
    assert is_locator_failure("Error: strict mode violation: locator('button') resolved to 2 elements")

    # Non-locator errors
    assert not is_locator_failure(None)
    assert not is_locator_failure("")
    assert not is_locator_failure("JSON 解析失败")
    assert not is_locator_failure("HTTP 500 Internal Server Error")


def test_generate_candidate_selectors_rules():
    # Rule 1: ID with dynamic suffix
    cands1 = generate_candidate_selectors("click", {"selector": "#submit-btn_12345"})
    assert "[id*='submit-btn']" in cands1
    assert "button[id*='submit-btn']" in cands1

    # Rule 2: Text hint in params or selector
    cands2 = generate_candidate_selectors("click", {"selector": "#unknown", "text": "登录"})
    assert "button:has-text('登录')" in cands2
    assert "text=登录" in cands2

    # Rule 3: Form placeholder
    cands3 = generate_candidate_selectors("fill", {"selector": "#input_user", "placeholder": "请输入用户名"})
    assert "[placeholder='请输入用户名']" in cands3

    # Rule 4: Data test id
    cands4 = generate_candidate_selectors("click", {"selector": "#btn", "data-testid": "submit-action"})
    assert "[data-testid='submit-action']" in cands4


def test_runtime_healer_recovers_step():
    healer = RuntimeLocatorHealer(max_heals_per_run=2)
    healer.reset_run(1)

    attempted_selectors = []

    async def fake_execute_step(_page, _action, params, _timeout):
        sel = params.get("selector")
        attempted_selectors.append(sel)
        if sel == "button:has-text('提交')":
            return {"success": True, "data": {"clicked": True}}
        return {"success": False, "error": "waiting for locator failed"}

    res = asyncio.run(
        healer.attempt_heal_and_retry(
            page=None,
            action="click",
            params={"selector": "#btn_v1", "text": "提交"},
            timeout_ms=5000,
            run_id=1,
            step_index=0,
            execute_step_fn=fake_execute_step,
        )
    )

    assert res is not None
    assert res["success"] is True
    assert res["data"]["healed_info"]["healed"] is True
    assert res["data"]["healed_info"]["healed_selector"] == "button:has-text('提交')"
    assert healer.get_heals_count(1) == 1


def test_runtime_healer_respects_quota():
    healer = RuntimeLocatorHealer(max_heals_per_run=1)
    healer.reset_run(2)

    async def fake_success(*_args):
        return {"success": True}

    # First heal succeeds and consumes quota
    res1 = asyncio.run(
        healer.attempt_heal_and_retry(
            page=None,
            action="click",
            params={"selector": "#b1_123"},
            timeout_ms=5000,
            run_id=2,
            step_index=0,
            execute_step_fn=fake_success,
        )
    )
    assert res1 is not None
    assert healer.get_heals_count(2) == 1

    # Second heal exceeds quota of 1 -> returns None
    res2 = asyncio.run(
        healer.attempt_heal_and_retry(
            page=None,
            action="click",
            params={"selector": "#b2_456"},
            timeout_ms=5000,
            run_id=2,
            step_index=1,
            execute_step_fn=fake_success,
        )
    )
    assert res2 is None
