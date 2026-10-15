"""Enterprise OIDC / OAuth2 Identity Provider (IdP) Integration Service (T4.1).

Provides:
1. Standard OpenID Connect (OIDC) / OAuth2 Provider Configurations (Keycloak, Okta, ADFS, Azure AD).
2. Cryptographic state and nonce generation to prevent CSRF and replay attacks.
3. ID Token claims verification (issuer, audience, expiration, subject, email).
4. Auto-provisioning & linking of enterprise users into local ATP accounts.
5. In-memory / persistent registry of enterprise SSO identity providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import logging
import secrets
from typing import Any
import urllib.parse

from app.models.user import UserRole

logger = logging.getLogger(__name__)


@dataclass
class OidcProviderConfig:
    provider_id: str  # e.g. "keycloak", "okta", "adfs"
    name: str  # e.g. "Corporate Keycloak SSO"
    issuer: str
    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    scopes: list[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    enabled: bool = True
    default_role: UserRole = UserRole.tester

    def to_dict(self, mask_secret: bool = True) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "issuer": self.issuer,
            "client_id": self.client_id,
            "client_secret": "***REDACTED***" if mask_secret else self.client_secret,
            "authorization_endpoint": self.authorization_endpoint,
            "token_endpoint": self.token_endpoint,
            "userinfo_endpoint": self.userinfo_endpoint,
            "jwks_uri": self.jwks_uri,
            "scopes": self.scopes,
            "enabled": self.enabled,
            "default_role": self.default_role.value,
        }


# In-memory registry of configured IdP providers with built-in standard templates
_PROVIDERS: dict[str, OidcProviderConfig] = {
    "keycloak": OidcProviderConfig(
        provider_id="keycloak",
        name="Keycloak Enterprise SSO",
        issuer="https://sso.enterprise.internal/auth/realms/atp",
        client_id="atp-web-client",
        client_secret="sec_keycloak_demo_98234",
        authorization_endpoint="https://sso.enterprise.internal/auth/realms/atp/protocol/openid-connect/auth",
        token_endpoint="https://sso.enterprise.internal/auth/realms/atp/protocol/openid-connect/token",
        userinfo_endpoint="https://sso.enterprise.internal/auth/realms/atp/protocol/openid-connect/userinfo",
        jwks_uri="https://sso.enterprise.internal/auth/realms/atp/protocol/openid-connect/certs",
        enabled=True,
    ),
    "okta": OidcProviderConfig(
        provider_id="okta",
        name="Okta Identity Cloud",
        issuer="https://company.okta.com/oauth2/default",
        client_id="0oa98234atpClient",
        client_secret="sec_okta_demo_77213",
        authorization_endpoint="https://company.okta.com/oauth2/default/v1/authorize",
        token_endpoint="https://company.okta.com/oauth2/default/v1/token",
        userinfo_endpoint="https://company.okta.com/oauth2/default/v1/userinfo",
        jwks_uri="https://company.okta.com/oauth2/default/v1/keys",
        enabled=True,
    ),
}

# State session cache: state -> {"nonce": str, "provider_id": str, "created_at": float}
_AUTH_STATES: dict[str, dict[str, Any]] = {}


def register_oidc_provider(config: OidcProviderConfig) -> None:
    """Register or update an OIDC IdP provider configuration."""
    _PROVIDERS[config.provider_id] = config


def get_oidc_provider(provider_id: str) -> OidcProviderConfig | None:
    """Retrieve an OIDC provider configuration by its ID."""
    return _PROVIDERS.get(provider_id)


def list_oidc_providers(*, only_enabled: bool = False) -> list[OidcProviderConfig]:
    """List registered OIDC providers."""
    providers = list(_PROVIDERS.values())
    if only_enabled:
        return [p for p in providers if p.enabled]
    return providers


def generate_sso_authorization_url(
    provider_id: str,
    redirect_uri: str,
    *,
    custom_state: str | None = None,
) -> dict[str, str]:
    """Generate state, nonce, and the IdP authorization redirect URL."""
    provider = get_oidc_provider(provider_id)
    if not provider:
        raise ValueError(f"OIDC 身份提供商不存在: {provider_id}")
    if not provider.enabled:
        raise ValueError(f"OIDC 身份提供商已被禁用: {provider_id}")

    state = custom_state or secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)

    _AUTH_STATES[state] = {
        "nonce": nonce,
        "provider_id": provider_id,
        "redirect_uri": redirect_uri,
        "created_at": datetime.now(timezone.utc).timestamp(),
    }

    params = {
        "response_type": "code",
        "client_id": provider.client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(provider.scopes),
        "state": state,
        "nonce": nonce,
    }

    query_str = urllib.parse.urlencode(params)
    auth_url = f"{provider.authorization_endpoint}?{query_str}"

    return {
        "authorization_url": auth_url,
        "state": state,
        "nonce": nonce,
        "provider_id": provider_id,
    }


def verify_id_token_claims(
    claims: dict[str, Any],
    provider: OidcProviderConfig,
    *,
    expected_nonce: str | None = None,
) -> dict[str, Any]:
    """Verify standard OIDC ID token claims (iss, aud, exp, nonce, sub)."""
    # 1. Verify issuer
    iss = claims.get("iss")
    if iss != provider.issuer:
        raise ValueError(f"ID Token 颁发者不匹配: 期望 {provider.issuer}, 实际收到 {iss}")

    # 2. Verify audience
    aud = claims.get("aud")
    if isinstance(aud, list):
        if provider.client_id not in aud:
            raise ValueError(f"ID Token 受众不匹配: 期望包含 {provider.client_id}, 实际收到 {aud}")
    elif aud != provider.client_id:
        raise ValueError(f"ID Token 受众不匹配: 期望 {provider.client_id}, 实际收到 {aud}")

    # 3. Verify expiration
    now = datetime.now(timezone.utc).timestamp()
    exp = claims.get("exp")
    if exp is not None and float(exp) < now:
        raise ValueError(f"ID Token 已过期 (exp={exp}, now={now})")

    # 4. Verify nonce if expected
    if expected_nonce:
        nonce = claims.get("nonce")
        if nonce != expected_nonce:
            raise ValueError(f"ID Token Nonce 重放校验失败: 期望 {expected_nonce}, 实际收到 {nonce}")

    # 5. Extract subject and email
    sub = claims.get("sub")
    if not sub:
        raise ValueError("ID Token 缺少必需的主题声明 (sub)")

    email = claims.get("email") or f"{sub}@{provider.provider_id}.sso"
    username = claims.get("preferred_username") or claims.get("name") or str(sub)

    return {
        "sub": str(sub),
        "email": str(email).lower(),
        "username": str(username),
        "roles": claims.get("roles", []),
    }


def provision_sso_user_record(
    provider: OidcProviderConfig,
    verified_identity: dict[str, Any],
) -> dict[str, Any]:
    """Determine user provisioning payload for local ATP user mapping."""
    email = verified_identity["email"]
    sub = verified_identity["sub"]
    # Derive safe local username (avoid colons or spaces)
    base_name = verified_identity["username"].replace(" ", "_").replace(":", "_")
    username = f"sso_{provider.provider_id}_{base_name}"[:60]

    # Map external roles if present, else fallback to default_role
    roles = verified_identity.get("roles", [])
    assigned_role = provider.default_role
    if "admin" in roles:
        assigned_role = UserRole.admin
    elif "engineer" in roles:
        assigned_role = UserRole.engineer

    # Deterministic dummy password hash for SSO user
    sso_pwd_seed = f"sso_user_{provider.provider_id}_{sub}_{email}"
    hashed_pwd = hashlib.sha256(sso_pwd_seed.encode("utf-8")).hexdigest()

    return {
        "username": username,
        "email": email,
        "hashed_password": hashed_pwd,
        "role": assigned_role,
        "is_active": True,
        "provider_id": provider.provider_id,
        "external_sub": sub,
    }


def consume_auth_state(state: str) -> dict[str, Any]:
    """Retrieve and immediately invalidate state session to avoid replay attacks."""
    if state not in _AUTH_STATES:
        raise ValueError("无效或已过期的 SSO state 校验参数")
    return _AUTH_STATES.pop(state)
