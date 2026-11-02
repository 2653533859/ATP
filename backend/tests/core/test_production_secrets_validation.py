"""生产环境拒绝默认/示例密钥启动（P0-2）。"""

import pytest
from pydantic import ValidationError

from app.core import config

_PRIVATE_SECRET = "unit-test-private-secret-key-0123456789abcdef"
_PRIVATE_WEBHOOK = "unit-test-private-webhook-key"


@pytest.mark.parametrize("secret", sorted(config._PLACEHOLDER_APP_SECRET_KEYS))
def test_production_rejects_placeholder_app_secret_key(secret):
    with pytest.raises(ValidationError, match="APP_SECRET_KEY"):
        config.Settings(_env_file=None, APP_ENV="production", APP_SECRET_KEY=secret, WEBHOOK_API_KEY=_PRIVATE_WEBHOOK)


@pytest.mark.parametrize("key", sorted(config._PLACEHOLDER_WEBHOOK_API_KEYS))
def test_production_rejects_placeholder_webhook_api_key(key):
    with pytest.raises(ValidationError, match="WEBHOOK_API_KEY"):
        config.Settings(_env_file=None, APP_ENV="production", APP_SECRET_KEY=_PRIVATE_SECRET, WEBHOOK_API_KEY=key)


def test_production_accepts_private_secrets():
    settings = config.Settings(
        _env_file=None, APP_ENV="production", APP_SECRET_KEY=_PRIVATE_SECRET, WEBHOOK_API_KEY=_PRIVATE_WEBHOOK
    )
    assert settings.APP_ENV == "production"


def test_non_production_profiles_keep_default_secrets(monkeypatch):
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    monkeypatch.delenv("WEBHOOK_API_KEY", raising=False)
    settings = config.Settings(_env_file=None, APP_ENV="development")
    assert settings.APP_SECRET_KEY == "dev-secret-key-change-in-production"
    assert settings.WEBHOOK_API_KEY == "atp-webhook-key-change-in-production"
