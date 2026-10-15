"""Unit tests for T4.1 Enterprise OIDC / OAuth2 SSO Identity Provider Integration.

Tests:
1. Built-in OIDC IdP providers (Keycloak, Okta) registration and secret masking
2. Custom OIDC provider dynamic registration (ADFS / Azure AD)
3. Authorization URL generation with cryptographic state & nonce
4. ID token claims verification (issuer, audience, expiration, nonce, sub)
5. Anti-CSRF state consumption & replay prevention
6. User provisioning payload derivation and role mapping
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.models.user import UserRole
from app.services.oidc_sso_provider import (
    OidcProviderConfig,
    consume_auth_state,
    generate_sso_authorization_url,
    get_oidc_provider,
    list_oidc_providers,
    provision_sso_user_record,
    register_oidc_provider,
    verify_id_token_claims,
)


def test_builtin_and_custom_oidc_providers():
    # 1. Built-in Keycloak & Okta
    providers = list_oidc_providers()
    provider_ids = [p.provider_id for p in providers]
    assert "keycloak" in provider_ids
    assert "okta" in provider_ids

    kc = get_oidc_provider("keycloak")
    assert kc is not None
    assert kc.issuer == "https://sso.enterprise.internal/auth/realms/atp"
    dict_repr = kc.to_dict(mask_secret=True)
    assert dict_repr["client_secret"] == "***REDACTED***"

    # 2. Register custom ADFS provider
    adfs_cfg = OidcProviderConfig(
        provider_id="adfs_corp",
        name="Corp Active Directory Federation Services",
        issuer="https://adfs.corp.internal/adfs",
        client_id="atp-adfs-client",
        client_secret="sec_adfs_private_9918",
        authorization_endpoint="https://adfs.corp.internal/adfs/oauth2/authorize",
        token_endpoint="https://adfs.corp.internal/adfs/oauth2/token",
        userinfo_endpoint="https://adfs.corp.internal/adfs/userinfo",
        jwks_uri="https://adfs.corp.internal/adfs/discovery/keys",
        default_role=UserRole.engineer,
    )
    register_oidc_provider(adfs_cfg)

    retrieved = get_oidc_provider("adfs_corp")
    assert retrieved is not None
    assert retrieved.name == "Corp Active Directory Federation Services"
    assert retrieved.default_role == UserRole.engineer


def test_generate_sso_authorization_url_and_state_consumption():
    res = generate_sso_authorization_url(
        provider_id="keycloak",
        redirect_uri="http://localhost:5174/sso/callback",
    )
    assert "authorization_url" in res
    assert "response_type=code" in res["authorization_url"]
    assert "client_id=atp-web-client" in res["authorization_url"]
    assert res["state"] in res["authorization_url"]
    assert res["nonce"] in res["authorization_url"]

    # Invalidate / consume state
    state_data = consume_auth_state(res["state"])
    assert state_data["nonce"] == res["nonce"]
    assert state_data["provider_id"] == "keycloak"

    # Replay attempt fails
    with pytest.raises(ValueError, match="无效或已过期的 SSO state"):
        consume_auth_state(res["state"])


def test_verify_id_token_claims_success_and_failures():
    kc = get_oidc_provider("keycloak")
    assert kc is not None

    future_exp = datetime.now(timezone.utc).timestamp() + 3600
    past_exp = datetime.now(timezone.utc).timestamp() - 60

    valid_claims = {
        "iss": kc.issuer,
        "aud": kc.client_id,
        "exp": future_exp,
        "sub": "user_emp_1001",
        "email": "alice@enterprise.internal",
        "preferred_username": "alice_wong",
        "nonce": "test_nonce_123",
        "roles": ["engineer"],
    }

    # 1. Success
    verified = verify_id_token_claims(valid_claims, kc, expected_nonce="test_nonce_123")
    assert verified["sub"] == "user_emp_1001"
    assert verified["email"] == "alice@enterprise.internal"
    assert verified["username"] == "alice_wong"
    assert "engineer" in verified["roles"]

    # 2. Issuer mismatch
    bad_iss_claims = dict(valid_claims, iss="https://evil.idp.com")
    with pytest.raises(ValueError, match="颁发者不匹配"):
        verify_id_token_claims(bad_iss_claims, kc)

    # 3. Audience mismatch
    bad_aud_claims = dict(valid_claims, aud="wrong-client-app")
    with pytest.raises(ValueError, match="受众不匹配"):
        verify_id_token_claims(bad_aud_claims, kc)

    # 4. Expired token
    expired_claims = dict(valid_claims, exp=past_exp)
    with pytest.raises(ValueError, match="已过期"):
        verify_id_token_claims(expired_claims, kc)

    # 5. Nonce mismatch
    with pytest.raises(ValueError, match="Nonce 重放校验失败"):
        verify_id_token_claims(valid_claims, kc, expected_nonce="different_nonce")


def test_provision_sso_user_record():
    kc = get_oidc_provider("keycloak")
    assert kc is not None

    verified_identity = {
        "sub": "kc_emp_9901",
        "email": "bob@enterprise.internal",
        "username": "bob smith",
        "roles": ["admin"],
    }

    user_dict = provision_sso_user_record(kc, verified_identity)
    assert user_dict["email"] == "bob@enterprise.internal"
    assert "sso_keycloak_" in user_dict["username"]
    assert user_dict["role"] == UserRole.admin
    assert user_dict["is_active"] is True
    assert user_dict["provider_id"] == "keycloak"
    assert user_dict["external_sub"] == "kc_emp_9901"
