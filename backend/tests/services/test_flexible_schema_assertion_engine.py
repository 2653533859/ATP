"""Unit tests for D2.2 Flexible Schema Assertion Engine Service."""

import pytest

from app.services.flexible_schema_assertion_engine import (
    AssertionToleranceMode,
    FlexibleAssertionConfig,
    SchemaDriftType,
    assert_flexible_schema,
    list_assertion_audits,
    reset_assertion_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_assertion_registry()
    yield
    reset_assertion_registry()


def test_assert_flexible_schema_compatible_with_extra_fields():
    expected_schema = {
        "type": "object",
        "required": ["order_id", "amount"],
        "properties": {
            "order_id": {"type": "string"},
            "amount": {"type": "number"},
        },
    }

    # 实际返回新增了 extra field: "coupon_code"
    actual_payload = {
        "order_id": "ORD-12345",
        "amount": 99.5,
        "coupon_code": "PROMO2026",
    }

    res = assert_flexible_schema(
        expected_schema=expected_schema,
        actual_payload=actual_payload,
        config=FlexibleAssertionConfig(mode=AssertionToleranceMode.COMPATIBLE),
    )

    assert res.passed is True
    assert res.total_drifts_count == 1
    drift = res.drifts[0]
    assert drift.drift_type == SchemaDriftType.EXTRA_FIELD
    assert drift.field_path == "coupon_code"
    assert drift.is_breaking is False

    # 校验自愈版 Schema 自动纳入了 coupon_code
    assert res.autofixed_schema is not None
    assert "coupon_code" in res.autofixed_schema["properties"]
    assert res.autofixed_schema["properties"]["coupon_code"]["type"] == "string"


def test_assert_flexible_schema_strict_fails_on_extra_fields():
    expected_schema = {
        "type": "object",
        "required": ["code"],
        "properties": {
            "code": {"type": "integer"},
        },
    }

    actual_payload = {
        "code": 200,
        "unexpected_token": "secret_abc",
    }

    res = assert_flexible_schema(
        expected_schema=expected_schema,
        actual_payload=actual_payload,
        config=FlexibleAssertionConfig(mode=AssertionToleranceMode.STRICT),
    )

    assert res.passed is False
    assert any(d.is_breaking and d.drift_type == SchemaDriftType.EXTRA_FIELD for d in res.drifts)


def test_assert_flexible_schema_missing_required_field_fails():
    expected_schema = {
        "type": "object",
        "required": ["user_id", "email"],
        "properties": {
            "user_id": {"type": "integer"},
            "email": {"type": "string"},
        },
    }

    # 缺失必填字段 email
    actual_payload = {
        "user_id": 1001,
    }

    res = assert_flexible_schema(
        expected_schema=expected_schema,
        actual_payload=actual_payload,
    )

    assert res.passed is False
    assert any(d.is_breaking and d.drift_type == SchemaDriftType.MISSING_FIELD for d in res.drifts)


def test_assert_flexible_schema_lenient_numeric_coercion():
    expected_schema = {
        "type": "object",
        "required": ["price"],
        "properties": {
            "price": {"type": "number"},
        },
    }

    # 实际返回字符串数字 "199.9"
    actual_payload = {
        "price": "199.9",
    }

    # 在宽松模式下允许字符串强转
    res = assert_flexible_schema(
        expected_schema=expected_schema,
        actual_payload=actual_payload,
        config=FlexibleAssertionConfig(mode=AssertionToleranceMode.LENIENT, allow_numeric_string_coercion=True),
    )

    assert res.passed is True
    assert any(d.drift_type == SchemaDriftType.TYPE_DRIFT and not d.is_breaking for d in res.drifts)


def test_nested_object_autofix_and_history():
    expected_schema = {
        "type": "object",
        "properties": {
            "meta": {
                "type": "object",
                "properties": {
                    "trace_id": {"type": "string"},
                },
            },
        },
    }

    actual_payload = {
        "meta": {
            "trace_id": "tr_112233",
            "span_id": "sp_9988",
        },
    }

    res = assert_flexible_schema(
        expected_schema=expected_schema,
        actual_payload=actual_payload,
        config=FlexibleAssertionConfig(mode=AssertionToleranceMode.COMPATIBLE),
    )

    assert res.passed is True
    assert res.autofixed_schema is not None
    assert "span_id" in res.autofixed_schema["properties"]["meta"]["properties"]

    # 验证审计历史写入
    history = list_assertion_audits()
    assert len(history) == 1
    assert history[0].audit_id.startswith("drift_audit_")
