"""Trace 采样调谐与敏感数据脱敏服务单测 (T4.1)"""

from __future__ import annotations

from app.services.trace_sampler_and_sanitizer import (
    SamplerConfig,
    SamplerStrategy,
    sanitize_span,
    sanitize_text,
    should_sample_trace,
    update_sampler_config,
)


def test_sampler_decisions():
    # 1. 强制常开与常关
    on_cfg = SamplerConfig(strategy=SamplerStrategy.ALWAYS_ON)
    assert should_sample_trace("trace_01", config=on_cfg)[0] is True

    off_cfg = SamplerConfig(strategy=SamplerStrategy.ALWAYS_OFF)
    assert should_sample_trace("trace_01", config=off_cfg)[0] is False

    # 2. 失败优先策略 (Error Priority)
    err_cfg = SamplerConfig(strategy=SamplerStrategy.ERROR_PRIORITY, force_sample_errors=True)
    assert should_sample_trace("trace_02", is_error=True, config=err_cfg)[0] is True
    assert should_sample_trace("trace_02", is_error=False, config=err_cfg)[0] is False

    # 3. 慢调用优先策略
    slow_cfg = SamplerConfig(strategy=SamplerStrategy.ADAPTIVE, slow_span_threshold_ms=100.0)
    assert should_sample_trace("trace_03", duration_ms=150.0, config=slow_cfg)[0] is True

    # 4. 概率采样确定性验证
    prob_cfg = SamplerConfig(strategy=SamplerStrategy.PROBABILISTIC, base_sample_rate=1.0)
    assert should_sample_trace("trace_04", config=prob_cfg)[0] is True


def test_sanitize_sensitive_credentials():
    # 1. Bearer Token 与 API Key 脱敏
    raw = "GET /api/v1?token=secret_jwt_xyz Authorization: Bearer abcdef123456"
    cleaned = sanitize_text(raw)
    assert "abcdef123456" not in cleaned
    assert "Bearer ******" in cleaned
    assert "token=******" in cleaned

    # 2. 个人隐私 PII (身份证与手机号) 脱敏
    pii_raw = "User info: 110101199003072345 and phone 13812345678"
    pii_cleaned = sanitize_text(pii_raw)
    assert "110101********2345" in pii_cleaned
    assert "138****5678" in pii_cleaned


def test_sanitize_span_attributes():
    span = {
        "span_id": "span_pay_01",
        "name": "POST /api/pay?password=my_secret_pwd",
        "service_name": "payment-api",
        "attributes": {
            "http.url": "https://pay.internal/auth?api_key=sk-123456789",
            "password": "plain_password",
            "user.id_card": "440102198506151234",
            "db.statement": "SELECT * FROM users WHERE password = 'plain_password'",
        },
        "status": {
            "code": "ERROR",
            "message": "Auth failed with token secret_token_xyz",
        },
    }

    sanitized = sanitize_span(span)
    attrs = sanitized["attributes"]

    assert "my_secret_pwd" not in sanitized["name"]
    assert "sk-123456789" not in attrs["http.url"]
    assert attrs["password"] == "******"
    assert "440102********1234" in attrs["user.id_card"]
    assert "secret_token_xyz" not in sanitized["status"]["message"]


def test_update_sampler_config():
    cfg = update_sampler_config(
        strategy="ERROR_PRIORITY",
        base_sample_rate=0.25,
        slow_span_threshold_ms=80.0,
    )
    assert cfg.strategy == SamplerStrategy.ERROR_PRIORITY
    assert cfg.base_sample_rate == 0.25
    assert cfg.slow_span_threshold_ms == 80.0

    # 还原为默认 ADAPTIVE
    update_sampler_config(strategy="ADAPTIVE", base_sample_rate=0.5, slow_span_threshold_ms=100.0)
