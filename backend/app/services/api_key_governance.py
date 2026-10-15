"""API Key and Tenant Token Governance Service (T4.2).

Provides:
1. Secure API key generation (raw key returned once; SHA-256 hash stored).
2. Lifecycle expiration and CIDR/IP allowlist access control.
3. Fast lookup and usage tracking (last_used_at, last_used_ip, total_calls).
4. Security compliance audit report generation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import logging
import secrets
from typing import Any

from sqlalchemy import select

from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)


def is_ip_allowed(client_ip: str | None, allowlist: list[str]) -> bool:
    """Check whether a client IP matches an explicit allowlist of IPs or CIDR networks."""
    cleaned_allowlist = [str(item).strip() for item in allowlist if str(item).strip()]
    if not cleaned_allowlist:
        return True
    if not client_ip:
        return False

    try:
        ip_obj = ipaddress.ip_address(client_ip.strip())
    except ValueError:
        return False

    for rule in cleaned_allowlist:
        try:
            if "/" in rule:
                if ip_obj in ipaddress.ip_network(rule, strict=False):
                    return True
            else:
                if ip_obj == ipaddress.ip_address(rule):
                    return True
        except ValueError:
            continue

    return False


async def generate_api_key(
    db: Any,
    *,
    name: str,
    user_id: int,
    project_id: int | None = None,
    environment_id: int | None = None,
    role: str = "engineer",
    ip_allowlist: list[str] | None = None,
    expires_in_days: int | None = None,
) -> tuple[ApiKey, str]:
    """Generate a new secure API key and persist its SHA-256 hash."""
    now = datetime.now(timezone.utc)
    raw_token = f"atp_sec_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    key_prefix = f"{raw_token[:10]}..."

    expires_at = None
    if expires_in_days and expires_in_days > 0:
        expires_at = now + timedelta(days=expires_in_days)

    cleaned_ips = [str(ip).strip() for ip in (ip_allowlist or []) if str(ip).strip()]

    api_key = ApiKey(
        name=name.strip(),
        key_hash=key_hash,
        key_prefix=key_prefix,
        user_id=user_id,
        project_id=project_id,
        environment_id=environment_id,
        role=role,
        ip_allowlist=cleaned_ips,
        expires_at=expires_at,
        is_active=True,
        total_calls=0,
    )
    db.add(api_key)
    await db.flush()
    return api_key, raw_token


async def validate_api_key(
    db: Any,
    raw_key: str,
    client_ip: str | None = None,
) -> ApiKey | None:
    """Validate a raw API key against stored active hashes, expiration, and IP rules."""
    if not raw_key or not isinstance(raw_key, str):
        return None

    key_hash = hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()
    query = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)  # noqa: E712
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if api_key is None:
        return None

    now = datetime.now(timezone.utc)
    if api_key.expires_at and api_key.expires_at <= now:
        logger.info("API Key %s expired on %s", api_key.key_prefix, api_key.expires_at)
        return None

    if not is_ip_allowed(client_ip, api_key.ip_allowlist or []):
        logger.warning(
            "API Key %s rejected: client IP %s not in allowlist %s",
            api_key.key_prefix,
            client_ip,
            api_key.ip_allowlist,
        )
        return None

    # Track usage
    api_key.last_used_at = now
    api_key.last_used_ip = str(client_ip)[:64] if client_ip else None
    api_key.total_calls = (api_key.total_calls or 0) + 1
    await db.flush()
    return api_key


async def revoke_api_key(
    db: Any,
    key_id: int,
    user_id: int,
    *,
    is_admin: bool = False,
) -> bool:
    """Revoke an active API key."""
    api_key = await db.get(ApiKey, key_id)
    if api_key is None:
        return False
    if not is_admin and api_key.user_id != user_id:
        return False

    api_key.is_active = False
    await db.flush()
    return True


async def export_api_key_audit_report(
    db: Any,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    """Generate a security compliance audit report of all managed API keys."""
    query = select(ApiKey).order_by(ApiKey.created_at.desc())
    if project_id is not None:
        query = query.where(ApiKey.project_id == project_id)

    result = await db.execute(query)
    keys = result.scalars().all()
    now = datetime.now(timezone.utc)

    report: list[dict[str, Any]] = []
    for k in keys:
        is_expired = bool(k.expires_at and k.expires_at <= now)
        report.append(
            {
                "key_id": k.id,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "user_id": k.user_id,
                "project_id": k.project_id,
                "environment_id": k.environment_id,
                "role": k.role,
                "ip_allowlist": k.ip_allowlist or [],
                "has_ip_restriction": len(k.ip_allowlist or []) > 0,
                "is_active": k.is_active,
                "is_expired": is_expired,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "total_calls": k.total_calls or 0,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "last_used_ip": k.last_used_ip,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            }
        )
    return report
