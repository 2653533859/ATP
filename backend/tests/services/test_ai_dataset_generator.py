import asyncio
from types import SimpleNamespace

from app.services import ai_dataset_generator as generator
from app.services.ai_dataset_generator import _parse_rows, infer_schema_fields


def test_parse_rows_accepts_json_fence_and_limits_rows():
    rows, warnings = _parse_rows('```json\n[{"id": 1}, {"id": 2}]\n```', 1)

    assert rows == [{"id": 1}]
    assert warnings == ["AI 返回了 2 行，已按请求限制保留前 1 行"]


def test_parse_rows_accepts_rows_wrapper_and_rejects_scalars():
    rows, _ = _parse_rows('{"rows": [{"ok": true}]}', 2)
    assert rows == [{"ok": True}]

    try:
        _parse_rows("[1, 2]", 2)
    except ValueError as exc:
        assert "对象数组" in str(exc)
    else:
        raise AssertionError("expected object-array validation error")


def test_infer_schema_fields_uses_stable_first_seen_order_and_types():
    fields = infer_schema_fields([{"name": "demo", "age": 18, "enabled": True}, {"age": 19, "name": "next"}])

    assert [field["name"] for field in fields] == ["name", "age", "enabled"]
    assert [field["type"] for field in fields] == ["string", "integer", "boolean"]


def test_generate_dataset_rows_decrypts_checks_quota_and_calls_llm(monkeypatch):
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
        return SimpleNamespace(text='[{"email": "synthetic@example.test", "age": 20}]')

    monkeypatch.setattr(generator, "check_and_incr_daily_limit", allow_quota)
    monkeypatch.setattr(generator, "call_llm", fake_call)

    rows, schema, warnings = asyncio.run(
        generator.generate_dataset_rows(
            config=config,
            schema_fields=[],
            requirement="生成测试用户",
            row_count=1,
        )
    )

    assert rows == [{"email": "synthetic@example.test", "age": 20}]
    assert [field["name"] for field in schema] == ["email", "age"]
    assert warnings == []
    assert captured["request"].api_key == "decrypted:encrypted"
    assert captured["request"].model_name == "test-model"
