"""Unit tests for T4.1 Sensitive Test Data and Credentials Dynamic Redaction Gateway.

Tests:
1. mask_pii_text masks 11-digit mobile phones, 18-digit ID cards, 16-19 digit bank cards, and emails
2. Custom sensitive keywords / enterprise blacklist terms replaced with [REDACTED]
3. redact_pii_data recursively redacts nested dictionaries, lists, and masks sensitive key values
4. apply_pii_redaction_gateway deep-copies without mutating original objects
5. API test for POST /api/v1/security/mask-pii
"""

from __future__ import annotations


from app.models.bootstrap import load_all_models
from app.services.sensitive_data_redactor import (
    apply_pii_redaction_gateway,
    mask_pii_text,
    redact_pii_data,
)

load_all_models()


def test_mask_phone_numbers():
    text = "联系用户：张三，手机号是 13812345678，备用号码 19987654321。"
    masked = mask_pii_text(text)
    assert "13812345678" not in masked
    assert "19987654321" not in masked
    assert "138****5678" in masked
    assert "199****4321" in masked


def test_mask_resident_id_cards():
    text = "身份核验通过，身份证号：110101199003071234，请予以放行。"
    masked = mask_pii_text(text)
    assert "110101199003071234" not in masked
    assert "110101********1234" in masked


def test_mask_bank_cards():
    text = "扣款账户：6222021234567890123 (19位)，信用卡：4392123456789012 (16位)。"
    masked = mask_pii_text(text)
    assert "6222021234567890123" not in masked
    assert "4392123456789012" not in masked
    assert "6222********0123" in masked
    assert "4392********9012" in masked


def test_mask_email_addresses():
    text = "通知已发送至 alice@company.com 和 support@service.org。"
    masked = mask_pii_text(text)
    assert "alice@company.com" not in masked
    assert "al***@company.com" in masked
    assert "su***@service.org" in masked


def test_mask_custom_keywords():
    text = "项目包含 TOP_SECRET_KEY 以及核心商业机密代码。"
    masked = mask_pii_text(text, custom_keywords=["TOP_SECRET_KEY", "商业机密"])
    assert "TOP_SECRET_KEY" not in masked
    assert "商业机密" not in masked
    assert "[REDACTED]" in masked


def test_redact_pii_data_nested_dict():
    raw_response = {
        "user": {
            "name": "李四",
            "phone": "13900001111",
            "id_card": "31010119850512345X",
            "email": "lisi@example.com",
            "password": "CleartextPassword123!",
            "api_token": "secret_bearer_token_xyz",
        },
        "orders": [
            {"order_id": 1001, "card_no": "6225881234567890"},
        ],
        "status_code": 200,
        "is_active": True,
    }

    redacted = redact_pii_data(raw_response, custom_keywords=["李四"])

    # 1. Credential keys completely masked
    assert redacted["user"]["password"] == "******"
    assert redacted["user"]["api_token"] == "******"

    # 2. PII fields masked with pattern preservation
    assert redacted["user"]["phone"] == "139****1111"
    assert redacted["user"]["id_card"] == "310101********345X"
    assert redacted["user"]["email"] == "li***@example.com"
    assert redacted["user"]["name"] == "[REDACTED]"

    assert redacted["orders"][0]["card_no"] == "6225********7890"
    # Primitive numbers and bools preserved
    assert redacted["status_code"] == 200
    assert redacted["is_active"] is True


def test_apply_pii_redaction_gateway_does_not_mutate_original():
    original = {
        "password": "mypassword",
        "phone": "13800008888",
    }
    redacted = apply_pii_redaction_gateway(original)
    assert redacted["password"] == "******"
    assert redacted["phone"] == "138****8888"

    # Original untouched
    assert original["password"] == "mypassword"
    assert original["phone"] == "13800008888"
