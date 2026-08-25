"""AI governance helpers keep provider output bounded and non-sensitive."""

from app.services.ai_governance import redact_llm_text


def test_redact_llm_text_masks_sensitive_json_fields_and_embedded_values():
    safe = redact_llm_text('{"password":"secret","notes":"token=raw-secret"}')

    assert "secret" not in safe
    assert "raw-secret" not in safe
    assert "[已脱敏]" in safe


def test_redact_llm_text_masks_url_credentials_and_query_secrets():
    safe = redact_llm_text("https://user:password@example.test/api?access_token=secret")

    assert "password" not in safe
    assert "secret" not in safe
    assert "<redacted>" in safe


def test_redact_llm_text_limits_provider_output():
    assert len(redact_llm_text("x" * 20, limit=8)) == 8
