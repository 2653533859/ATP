"""AI 用例生成服务的供应商密钥边界回归。"""

import asyncio
from types import SimpleNamespace

from app.services.ai_case import generator


def test_generate_case_drafts_allows_keyless_ollama(monkeypatch):
    config = SimpleNamespace(
        enabled=True,
        api_key_encrypted="",
        provider="ollama",
        model_name="qwen3",
        endpoint="http://ollama:11434",
        default_params={},
    )
    captured = {}

    async def allow_quota(**_kwargs):
        return True

    async def fake_call(request):
        captured["request"] = request
        return SimpleNamespace(text='[{"name":"本地登录用例","steps":[{"action":"请求登录接口"}]}]')

    monkeypatch.setattr(generator, "check_and_incr_daily_limit", allow_quota)
    monkeypatch.setattr(generator, "call_llm", fake_call)

    result = asyncio.run(
        generator.generate_case_drafts(
            config=config,
            endpoints=[{"method": "POST", "path": "/login"}],
            user_requirement="生成本地登录用例",
            case_type="api",
            priority="P1",
            case_level="core",
            max_cases=1,
        )
    )

    assert result.drafts[0]["name"] == "本地登录用例"
    assert captured["request"].api_key == ""


def test_generate_case_drafts_keeps_keyless_non_ollama_rejected(monkeypatch):
    config = SimpleNamespace(
        enabled=True,
        api_key_encrypted="",
        provider="openai",
        model_name="gpt-test",
        endpoint="https://llm.example.test/v1",
        default_params={},
    )

    async def allow_quota(**_kwargs):
        return True

    monkeypatch.setattr(generator, "check_and_incr_daily_limit", allow_quota)

    try:
        asyncio.run(
            generator.generate_case_drafts(
                config=config,
                endpoints=[],
                user_requirement="生成用例",
                case_type="api",
                priority="P1",
                case_level="core",
                max_cases=1,
            )
        )
    except ValueError as exc:
        assert "API Key 解密失败" in str(exc)
    else:
        raise AssertionError("expected malformed non-Ollama configuration to remain rejected")
