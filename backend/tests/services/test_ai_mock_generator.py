import asyncio
from types import SimpleNamespace

from app.services import ai_mock_generator as generator
from app.models.mock import MockMethod


def _source_rule():
    return SimpleNamespace(
        id=8,
        name="Users",
        method=MockMethod.GET,
        path="/api/users",
        status_code=200,
        response_headers={"Content-Type": "application/json"},
        response_body='{"ok": true}',
        match_conditions={"query": {}, "headers": {}, "body": {}},
        delay_ms=0,
        recorded_samples=[],
    )


def test_parse_json_array_coerces_rule_defaults_and_limits_results():
    rules = generator._parse_json_array(
        '```json\n[{"name":"Users","method":"invalid","path":"api/users","response_body":{"ok":true}}, {"name":"ignored","path":"/ignored"}]\n```',
        1,
    )

    assert rules == [
        {
            "name": "Users",
            "method": "GET",
            "path": "/api/users",
            "status_code": 200,
            "response_headers": {"Content-Type": "application/json"},
            "response_body": '{"ok": true}',
            "match_conditions": {"query": {}, "headers": {}, "body": {}},
            "delay_ms": 0,
            "is_enabled": True,
            "render_template": False,
            "record_requests": False,
        }
    ]


def test_parse_json_array_rejects_scalar_items():
    try:
        generator._parse_json_array("[1]", 1)
    except ValueError as exc:
        assert "对象数组" in str(exc)
    else:
        raise AssertionError("expected object-array validation error")


def test_parse_json_array_rejects_empty_malformed_and_oversized_output():
    for text, expected in (("", "返回为空"), ("not-json", "未找到"), ("[", "未找到"), ("[]", "有效 Mock")):
        try:
            generator._parse_json_array(text, 1)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("expected parser error")

    try:
        generator._parse_json_array('[{"response_body":"' + ("x" * (256 * 1024)) + '"}]', 1)
    except ValueError as exc:
        assert "256KB" in str(exc)
    else:
        raise AssertionError("expected size limit error")


def test_coerce_rule_normalizes_conditions_headers_and_invalid_numbers():
    rule = generator._coerce_rule(
        {
            "method": "POST",
            "path": "api/orders",
            "response_body": "ok",
            "match_conditions": {"query": {"page": 2, "empty": None}, "headers": "invalid", "body": {"paid": True}},
            "response_headers": {"X-Count": 2, "empty": None},
            "status_code": "invalid",
            "delay_ms": "invalid",
            "render_template": 1,
            "record_requests": 1,
        }
    )

    assert rule["match_conditions"] == {"query": {"page": "2"}, "headers": {}, "body": {"paid": "True"}}
    assert rule["response_headers"] == {"X-Count": "2"}
    assert rule["status_code"] == 200
    assert rule["delay_ms"] == 0


def test_generate_mock_rule_drafts_rejects_disabled_config_and_quota(monkeypatch):
    config = SimpleNamespace(enabled=False, api_key_encrypted="encrypted")
    try:
        asyncio.run(
            generator.generate_mock_rule_drafts(
                config=config,
                source_rules=[],
                requirement="",
                rule_count=1,
            )
        )
    except ValueError as exc:
        assert "禁用" in str(exc)
    else:
        raise AssertionError("expected disabled-config error")

    config.enabled = True
    monkeypatch.setattr(generator, "decrypt", lambda value: value)

    async def deny_quota(**_kwargs):
        return False

    monkeypatch.setattr(generator, "check_and_incr_daily_limit", deny_quota)
    try:
        asyncio.run(
            generator.generate_mock_rule_drafts(
                config=config,
                source_rules=[],
                requirement="",
                rule_count=1,
            )
        )
    except ValueError as exc:
        assert "上限" in str(exc)
    else:
        raise AssertionError("expected quota error")


def test_generate_mock_rule_drafts_redacts_context_and_calls_llm(monkeypatch):
    config = SimpleNamespace(
        enabled=True,
        api_key_encrypted="encrypted",
        provider="openai",
        model_name="test-model",
        endpoint="https://llm.example.test/v1",
        default_params={"temperature": 0.2},
    )
    captured = {}

    monkeypatch.setattr(generator, "decrypt", lambda value: f"decrypted:{value}")

    async def allow_quota(**_kwargs):
        return True

    async def fake_call(request):
        captured["request"] = request
        return SimpleNamespace(text='[{"name":"Generated users","path":"/api/users","response_body":{"ok":true}}]')

    monkeypatch.setattr(generator, "check_and_incr_daily_limit", allow_quota)
    monkeypatch.setattr(generator, "call_llm", fake_call)

    rules, warnings = asyncio.run(
        generator.generate_mock_rule_drafts(
            config=config,
            source_rules=[_source_rule()],
            requirement="生成成功响应",
            rule_count=1,
        )
    )

    assert rules[0]["path"] == "/api/users"
    assert warnings == []
    assert captured["request"].api_key == "decrypted:encrypted"
    assert "Users" in captured["request"].prompt
