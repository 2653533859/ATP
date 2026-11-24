"""Unit tests for AI and heuristic Web UI assertion suggestion."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.ai_case import AIWebAssertionSuggestIn, WebAssertionStepIn
from app.services.ai_case.web_assertion_suggestion import suggest_web_assertions


@pytest.mark.asyncio
async def test_suggest_web_assertions_heuristic_without_config() -> None:
    payload = AIWebAssertionSuggestIn(
        start_url="https://example.com/login",
        current_url="https://example.com/dashboard",
        page_title="工作台",
        dom_summary="菜单\n登录成功\n工作台概览",
        steps=[
            WebAssertionStepIn(action="goto", name="打开登录页", params={"url": "https://example.com/login"}),
            WebAssertionStepIn(action="click", name="点击登录", params={"selector": "button#login"}),
        ],
    )
    res = await suggest_web_assertions(payload, config=None, api_key="")
    assert res.source == "heuristic"
    assert len(res.assertions) >= 1
    assert res.assertions[0].action == "assert_text"
    assert res.assertions[0].params["text"] in {"登录成功", "工作台概览"}


@pytest.mark.asyncio
async def test_suggest_web_assertions_llm_parses_filters_and_redacts_password() -> None:
    config = SimpleNamespace(
        id=1,
        provider="openai",
        model_name="gpt-4o-mini",
        endpoint="https://api.example.com/v1",
        default_params={},
    )
    payload = AIWebAssertionSuggestIn(
        start_url="https://example.com/login",
        current_url="https://example.com/dashboard",
        page_title="控制台",
        dom_summary="欢迎回来，管理员\n退出登录",
        steps=[
            WebAssertionStepIn(
                action="fill", name="输入密码", params={"selector": "input[type=password]", "value": "SuperSecret123!"}
            ),
            WebAssertionStepIn(action="assert_text", name="已有断言", params={"text": "欢迎回来，管理员"}),
        ],
    )
    fake_llm_resp = SimpleNamespace(
        text="""```json
{
  "assertions": [
    {"action": "assert_text", "name": "重复断言", "params": {"text": "欢迎回来，管理员"}, "reason": "dup"},
    {"action": "assert_url", "name": "不支持的action", "params": {"url": "/dashboard"}, "reason": "bad"},
    {"action": "assert_text", "name": "断言登录状态", "params": {"text": "退出登录"}, "reason": "验证已登录"},
    {"action": "assert_visible", "name": "断言导航栏", "params": {"selector": "nav.main-nav"}, "reason": "验证主导航加载"}
  ]
}
```"""
    )

    with (
        patch(
            "app.services.ai_case.web_assertion_suggestion.check_and_incr_daily_limit", new=AsyncMock(return_value=True)
        ),
        patch(
            "app.services.ai_case.web_assertion_suggestion.call_llm", new=AsyncMock(return_value=fake_llm_resp)
        ) as mock_call,
    ):
        res = await suggest_web_assertions(payload, config=config, api_key="sk-test")

    assert res.source == "llm"
    assert [item.action for item in res.assertions] == ["assert_text", "assert_visible"]
    assert res.assertions[0].params == {"text": "退出登录"}
    assert res.assertions[1].params == {"selector": "nav.main-nav"}
    sent_prompt = mock_call.call_args.args[0].prompt
    assert "SuperSecret123!" not in sent_prompt
    assert "***" in sent_prompt


@pytest.mark.asyncio
async def test_suggest_web_assertions_llm_error_falls_back_to_heuristic() -> None:
    config = SimpleNamespace(
        id=2,
        provider="openai",
        model_name="gpt-4o-mini",
        endpoint=None,
        default_params={},
    )
    payload = AIWebAssertionSuggestIn(
        dom_summary="保存成功",
        steps=[WebAssertionStepIn(action="click", name="保存", params={"selector": "button.save"})],
    )
    with (
        patch(
            "app.services.ai_case.web_assertion_suggestion.check_and_incr_daily_limit", new=AsyncMock(return_value=True)
        ),
        patch(
            "app.services.ai_case.web_assertion_suggestion.call_llm", new=AsyncMock(side_effect=RuntimeError("timeout"))
        ),
    ):
        res = await suggest_web_assertions(payload, config=config, api_key="sk-test")

    assert res.source == "heuristic"
    assert len(res.assertions) == 1
    assert res.assertions[0].action == "assert_text"
    assert res.assertions[0].params == {"text": "保存成功"}
