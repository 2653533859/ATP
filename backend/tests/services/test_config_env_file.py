from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings


ROOT = Path(__file__).resolve().parents[3]


def test_settings_fall_back_to_repository_root_env_file():
    env_files = Settings.model_config["env_file"]

    assert Path(env_files[0]).resolve() == ROOT / ".env"
    assert env_files[1] == ".env"


def test_settings_reject_insecure_cross_site_auth_cookie():
    with pytest.raises(ValueError, match="APP_AUTH_COOKIE_SECURE"):
        Settings(APP_AUTH_COOKIE_SAMESITE="none", APP_AUTH_COOKIE_SECURE=False)


def test_settings_normalize_auth_cookie_samesite():
    configured = Settings(APP_AUTH_COOKIE_SAMESITE=" Strict ")

    assert configured.APP_AUTH_COOKIE_SAMESITE == "strict"


def test_audit_log_cleanup_is_opt_in_with_bounded_retention():
    configured = Settings(_env_file=None)

    assert configured.AUDIT_LOG_CLEANUP_ENABLED is False
    assert configured.AUDIT_LOG_RETENTION_DAYS == 365

    with pytest.raises(ValueError):
        Settings(_env_file=None, AUDIT_LOG_RETENTION_DAYS=0)
