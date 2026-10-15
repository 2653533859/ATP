"""Unit tests for T4.2 API Key / Tenant Token Governance and Security Audit Export.

Tests:
1. generate_api_key generates secure raw token and stores SHA-256 hash
2. is_ip_allowed checks exact IPs and CIDR block networks
3. validate_api_key tracks usage, checks expiration and IP restrictions
4. revoke_api_key revokes active key
5. export_api_key_audit_report exports compliance report
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.models.api_key import ApiKey
from app.models.bootstrap import load_all_models
from app.services.api_key_governance import (
    export_api_key_audit_report,
    generate_api_key,
    is_ip_allowed,
    revoke_api_key,
    validate_api_key,
)

load_all_models()
NOW = datetime.now(timezone.utc)


class _Result:
    def __init__(self, scalar=None, scalars_list=None):
        self.scalar = scalar
        self.scalars_list = scalars_list or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self.scalars_list)


class _FakeDB:
    def __init__(self, keys_by_id=None, keys_by_hash=None):
        self.keys_by_id = keys_by_id or {}
        self.keys_by_hash = keys_by_hash or {}
        self.added: list[Any] = []
        self.flushed = False

    async def get(self, model, obj_id):
        if model is ApiKey:
            return self.keys_by_id.get(obj_id)
        return None

    async def execute(self, statement):
        sql = str(statement).lower()
        compiled = getattr(statement, "compile", lambda: None)()
        params = getattr(compiled, "params", {}) or {}

        if "key_hash_1" in params or "key_hash" in params:
            target_hash = params.get("key_hash_1") or params.get("key_hash")
            key = self.keys_by_hash.get(target_hash)
            if key and not getattr(key, "is_active", True):
                return _Result(None)
            return _Result(key)

        if "from api_keys" in sql:
            keys = list(self.keys_by_id.values())
            proj = params.get("project_id_1") or params.get("project_id")
            if proj is not None:
                keys = [k for k in keys if getattr(k, "project_id", None) == proj]
            return _Result(scalars_list=keys)

        return _Result(None)

    def add(self, item):
        self.added.append(item)
        if getattr(item, "key_hash", None):
            if getattr(item, "id", None) is None:
                item.id = len(self.keys_by_id) + 1
            self.keys_by_id[item.id] = item
            self.keys_by_hash[item.key_hash] = item

    async def flush(self):
        self.flushed = True


def test_is_ip_allowed():
    # 1. Empty allowlist -> open to all
    assert is_ip_allowed("1.2.3.4", []) is True
    assert is_ip_allowed(None, []) is True

    # 2. Exact IP matching
    allowlist_exact = ["192.168.1.100", "10.0.0.1"]
    assert is_ip_allowed("192.168.1.100", allowlist_exact) is True
    assert is_ip_allowed("10.0.0.1", allowlist_exact) is True
    assert is_ip_allowed("192.168.1.101", allowlist_exact) is False
    assert is_ip_allowed("invalid-ip", allowlist_exact) is False
    assert is_ip_allowed(None, allowlist_exact) is False

    # 3. CIDR subnet matching
    allowlist_cidr = ["10.20.0.0/16", "172.16.0.0/24"]
    assert is_ip_allowed("10.20.1.55", allowlist_cidr) is True
    assert is_ip_allowed("172.16.0.99", allowlist_cidr) is True
    assert is_ip_allowed("10.21.0.1", allowlist_cidr) is False
    assert is_ip_allowed("192.168.1.1", allowlist_cidr) is False


@pytest.mark.asyncio
async def test_generate_and_validate_api_key_lifecycle():
    db: Any = _FakeDB()

    # 1. Generate Key with 30-day expiration and IP restriction
    api_key, raw_token = await generate_api_key(
        db,
        name="CI/CD Runner Key",
        user_id=1,
        project_id=10,
        role="engineer",
        ip_allowlist=["192.168.3.0/24"],
        expires_in_days=30,
    )

    assert raw_token.startswith("atp_sec_")
    assert api_key.name == "CI/CD Runner Key"
    assert api_key.key_prefix == f"{raw_token[:10]}..."
    assert api_key.is_active is True
    assert api_key.expires_at is not None
    assert api_key.expires_at > NOW + timedelta(days=29)
    assert db.flushed is True

    # 2. Validate valid key from allowed IP
    validated = await validate_api_key(db, raw_token, client_ip="192.168.3.50")
    assert validated is not None
    assert validated.id == api_key.id
    assert validated.total_calls == 1
    assert validated.last_used_ip == "192.168.3.50"
    assert validated.last_used_at is not None

    # 3. Validate from disallowed IP -> rejected
    disallowed = await validate_api_key(db, raw_token, client_ip="8.8.8.8")
    assert disallowed is None

    # 4. Unknown raw key -> rejected
    assert await validate_api_key(db, "atp_sec_nonexistent_key") is None


@pytest.mark.asyncio
async def test_validate_api_key_expired_or_revoked():
    db: Any = _FakeDB()

    # Expired key
    expired_key, raw_expired = await generate_api_key(
        db,
        name="Expired Token",
        user_id=2,
        expires_in_days=0,  # Expired immediately
    )
    expired_key.expires_at = NOW - timedelta(seconds=10)

    assert await validate_api_key(db, raw_expired) is None

    # Revoked key
    active_key, raw_active = await generate_api_key(db, name="Revoke Target", user_id=3)
    assert await validate_api_key(db, raw_active) is not None

    revoked = await revoke_api_key(db, active_key.id, user_id=3)
    assert revoked is True
    assert active_key.is_active is False
    assert await validate_api_key(db, raw_active) is None


@pytest.mark.asyncio
async def test_export_api_key_audit_report():
    db: Any = _FakeDB()
    await generate_api_key(
        db,
        name="Pipeline Token",
        user_id=1,
        project_id=42,
        ip_allowlist=["127.0.0.1"],
    )

    report = await export_api_key_audit_report(db, project_id=42)
    assert len(report) == 1
    item = report[0]
    assert item["name"] == "Pipeline Token"
    assert item["has_ip_restriction"] is True
    assert item["is_active"] is True
    assert item["is_expired"] is False
    assert "atp_sec_" in item["key_prefix"]
