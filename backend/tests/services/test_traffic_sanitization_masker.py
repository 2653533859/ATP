"""敏感数据实时脱敏与隐私字段掩码器单测 (T1.1)"""

from __future__ import annotations

from app.services.traffic_sanitization_masker import (
    SanitizationMode,
    SensitiveDataType,
    detect_value_sensitive_type,
    mask_sensitive_value,
    sanitize_traffic_payload,
)


def test_detect_sensitive_types():
    assert detect_value_sensitive_type("13812345678") == SensitiveDataType.PHONE
    assert detect_value_sensitive_type("110101199001011234") == SensitiveDataType.ID_CARD
    assert detect_value_sensitive_type("6222021234567890123") == SensitiveDataType.BANK_CARD
    assert detect_value_sensitive_type("alice@example.com") == SensitiveDataType.EMAIL
    assert detect_value_sensitive_type("my_secret_pwd", key_name="user_password") == SensitiveDataType.PASSWORD
    assert (
        detect_value_sensitive_type("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.do_signature")
        == SensitiveDataType.JWT_TOKEN
    )


def test_mask_modes():
    # 1. MASK 模式
    masked_phone = mask_sensitive_value("13812345678", SensitiveDataType.PHONE, SanitizationMode.MASK)
    assert masked_phone == "138****5678"

    masked_id = mask_sensitive_value("110101199001011234", SensitiveDataType.ID_CARD, SanitizationMode.MASK)
    assert masked_id == "110101********1234"

    masked_pwd = mask_sensitive_value("plaintext_pwd", SensitiveDataType.PASSWORD, SanitizationMode.MASK)
    assert masked_pwd == "[MASKED_PASSWORD]"

    # 2. HASH_SALT 模式
    hash_phone = mask_sensitive_value(
        "13812345678", SensitiveDataType.PHONE, SanitizationMode.HASH_SALT, salt="test_salt"
    )
    assert hash_phone.startswith("hash_")
    # 确定性加盐
    assert hash_phone == mask_sensitive_value(
        "13812345678", SensitiveDataType.PHONE, SanitizationMode.HASH_SALT, salt="test_salt"
    )

    # 3. SYNTHETIC_REPLACE 模式
    syn_phone = mask_sensitive_value("13812345678", SensitiveDataType.PHONE, SanitizationMode.SYNTHETIC_REPLACE)
    assert syn_phone.startswith("139")
    assert len(syn_phone) == 11


def test_sanitize_nested_payload():
    payload = {
        "headers": {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature",
            "Content-Type": "application/json",
        },
        "query": {
            "mobile": "13911112222",
            "page": 1,
        },
        "body": {
            "user": {
                "name": "张三",
                "id_card": "110101199001011234",
                "email": "zhangsan@company.org",
                "credentials": {
                    "password": "SuperSecretPassword!",
                },
            },
            "bank_cards": [
                "6222021234567890123",
            ],
            "tags": ["vip", "tester"],
        },
    }

    sanitized, audit = sanitize_traffic_payload(payload)

    # 查验脱敏结果
    assert sanitized["headers"]["Authorization"] == "Bearer [MASKED_TOKEN]"
    assert sanitized["headers"]["Content-Type"] == "application/json"
    assert sanitized["query"]["mobile"] == "139****2222"
    assert sanitized["body"]["user"]["id_card"] == "110101********1234"
    assert sanitized["body"]["user"]["email"] == "z***@company.org"
    assert sanitized["body"]["user"]["credentials"]["password"] == "[MASKED_PASSWORD]"
    assert sanitized["body"]["bank_cards"][0] == "622202******0123"
    assert sanitized["body"]["tags"] == ["vip", "tester"]

    # 查验审计元数据
    assert audit.masked_field_count == 6
    assert SensitiveDataType.PHONE in audit.detected_types
    assert SensitiveDataType.ID_CARD in audit.detected_types
    assert SensitiveDataType.PASSWORD in audit.detected_types
    assert SensitiveDataType.JWT_TOKEN in audit.detected_types
    assert SensitiveDataType.BANK_CARD in audit.detected_types
    assert SensitiveDataType.EMAIL in audit.detected_types

    d = audit.to_dict()
    assert d["masked_field_count"] == 6
    assert len(d["detected_types"]) == 6
