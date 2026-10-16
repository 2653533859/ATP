"""Unit tests for Traffic Data Masker Service (T1.2)."""

from __future__ import annotations

import json
import pytest

from app.services.traffic_data_masker import (
    batch_mask_traffic_items,
    hash_pseudonym,
    mask_captured_traffic_item,
    mask_payload_recursively,
    mask_text_content,
    reset_masking_rules,
    update_masking_rules,
)


@pytest.fixture(autouse=True)
def restore_rules():
    """每个测试前后重置为默认规则。"""
    reset_masking_rules()
    yield
    reset_masking_rules()


def test_mask_text_pii_patterns():
    """验证文本中各类 PII 敏感信息的正则自动识别与掩码。"""
    raw_text = (
        "用户手机号: 13812345678，身份证号: 110101199003071234，"
        "银行卡号: 6222021234567890123，邮箱: alice@example.com，"
        "认证凭据: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakSecret"
    )

    masked = mask_text_content(raw_text)

    # 1. 手机号校验
    assert "13812345678" not in masked
    assert "138****5678" in masked

    # 2. 身份证校验
    assert "110101199003071234" not in masked
    assert "110101********1234" in masked

    # 3. 银行卡校验
    assert "6222021234567890123" not in masked
    assert "6222********0123" in masked

    # 4. 邮箱校验
    assert "alice@example.com" not in masked
    assert "al***@example.com" in masked

    # 5. Bearer / JWT 凭证校验
    assert "doNotLeakSecret" not in masked
    assert "[REDACTED_AUTH_TOKEN]" in masked or "[REDACTED_JWT_TOKEN]" in masked


def test_hash_pseudonym_consistency():
    """验证 SHA-256 伪名化脱敏的一致性与不可逆性。"""
    val1 = "13912345678"
    val2 = "13912345678"
    val3 = "13987654321"

    hash1 = hash_pseudonym(val1)
    hash2 = hash_pseudonym(val2)
    hash3 = hash_pseudonym(val3)

    assert hash1 == hash2  # 同一个高敏手机号，伪名化后标识保持一致
    assert hash1 != hash3  # 不同手机号，伪名化后不同
    assert hash1.startswith("hash:")
    assert val1 not in hash1


def test_mask_payload_recursively():
    """验证对多层嵌套 dict / list / JSON 字符串的深度脱敏。"""
    payload = {
        "user_id": 1001,
        "password": "SuperSecretPassword123!",
        "profile": {
            "name": "张三",
            "phone": "13700001111",
            "email": "zhangsan@company.org",
        },
        "payment_cards": [
            {"card_no": "6214851234567890123", "cvv": "123"},
        ],
        "metadata_json_str": json.dumps({"inner_mobile": "13699998888", "token": "secret_abc"}),
    }

    masked = mask_payload_recursively(payload)

    # 密码必须完全抹除
    assert masked["password"] == "[REDACTED]"

    # 嵌套 profile 手机号与邮箱脱敏
    assert masked["profile"]["phone"] == "137****1111"
    assert masked["profile"]["email"] == "zh***@company.org"

    # 列表内银行卡脱敏
    assert "6214851234567890123" not in masked["payment_cards"][0]["card_no"]
    assert masked["payment_cards"][0]["cvv"] == "[REDACTED]"

    # 嵌套在 JSON 字符串内的敏感字段被成功解析并就地脱敏
    inner_parsed = json.loads(masked["metadata_json_str"])
    assert inner_parsed["inner_mobile"] == "136****8888"
    assert inner_parsed["token"] == "[REDACTED]"


def test_mask_captured_traffic_item():
    """验证对完整 CapturedTrafficItem 流量对象的全维度清洗。"""
    traffic_raw = {
        "traffic_id": "trf_sample_123",
        "protocol": "HTTP",
        "method": "POST",
        "path_or_endpoint": "/api/v1/user/bind-card",
        "headers": {
            "Authorization": "Bearer secret_jwt_token_1234567890",
            "X-Client-Version": "1.0.0",
        },
        "query_params": {
            "mobile": "13800002222",
        },
        "request_body": json.dumps(
            {
                "id_card": "110101199003071234",
                "card_no": "6222021234567890123",
                "password": "Password999",
            }
        ),
        "response_body": json.dumps(
            {
                "code": 0,
                "message": "绑定成功，银行短信已发送至 13800002222",
            }
        ),
        "tags": {"env": "prod"},
    }

    masked = mask_captured_traffic_item(traffic_raw)

    # Headers 脱敏
    assert "secret_jwt_token_1234567890" not in masked["headers"]["Authorization"]

    # Query 参数脱敏
    assert masked["query_params"]["mobile"] == "138****2222"

    # Request Body 脱敏
    req_body_parsed = json.loads(masked["request_body"])
    assert req_body_parsed["id_card"] == "110101********1234"
    assert req_body_parsed["card_no"] == "6222********0123"
    assert req_body_parsed["password"] == "[REDACTED]"

    # Response Body 脱敏
    resp_body_parsed = json.loads(masked["response_body"])
    assert "138****2222" in resp_body_parsed["message"]
    assert "13800002222" not in resp_body_parsed["message"]

    # 打标验证
    assert masked["tags"]["data_masked"] == "true"


def test_batch_masking_and_rules_update():
    """验证批量脱敏与规则热更新。"""
    items = [
        {"request_body": "phone is 13811112222"},
        {"request_body": "phone is 13933334444"},
    ]
    batch_res = batch_mask_traffic_items(items)
    assert len(batch_res) == 2
    assert "138****2222" in batch_res[0]["request_body"]
    assert "139****4444" in batch_res[1]["request_body"]

    # 更新规则为 HASH
    update_masking_rules(
        [
            {
                "rule_id": "rule_phone",
                "name": "手机号哈希伪名化",
                "category": "PHONE",
                "strategy": "HASH",
                "enabled": True,
            }
        ]
    )

    hashed_res = mask_text_content("用户电话: 13811112222")
    assert "tel_hash:" in hashed_res
    assert "13811112222" not in hashed_res
