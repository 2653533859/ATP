"""Build encrypted configuration snapshots with safe display copies."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access
from app.core.config import settings
from app.core.encryption import decrypt, decrypt_config, encrypt
from app.models.ai_llm_config import AILLMConfig
from app.models.environment import Environment, EnvVariable
from app.models.global_variable import GlobalVariable
from app.models.notification import NotificationConfig
from app.models.performance_node import PerformanceNode
from app.models.storage_policy import StoragePolicy
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole


SUPPORTED_SNAPSHOT_DOMAINS = frozenset(
    {
        "environment",
        "global_variable",
        "ai_llm",
        "storage_policy",
        "notification",
        "performance_node",
    }
)

_SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_-]?key|access[_-]?token|authorization|cookie|credential|endpoint|password|passwd|private[_-]?key|secret|token|url|webhook)",
    re.IGNORECASE,
)


class ConfigurationSnapshotError(Exception):
    """Base error for an invalid or inaccessible snapshot target."""


class ConfigurationSnapshotNotFound(ConfigurationSnapshotError):
    pass


class ConfigurationSnapshotForbidden(ConfigurationSnapshotError):
    pass


class ConfigurationSnapshotUnsupported(ConfigurationSnapshotError):
    pass


@dataclass(frozen=True)
class ConfigurationSnapshot:
    domain: str
    resource_id: int
    project_id: int | None
    resource_name: str
    payload: dict[str, Any]
    redacted_payload: dict[str, Any]
    fingerprint: str
    payload_encrypted: str


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(payload_json: str) -> str:
    # A keyed digest avoids exposing a plain hash of a low-entropy secret while
    # remaining stable across repeated snapshots of the same configuration.
    key = hashlib.sha256(settings.APP_SECRET_KEY.encode("utf-8")).digest()
    return hmac.new(key, payload_json.encode("utf-8"), hashlib.sha256).hexdigest()


def _decrypt_or_keep(value: str | None) -> tuple[str, bool]:
    if not value:
        return "", False
    try:
        return decrypt(value), False
    except Exception:
        # Older installations may contain plaintext legacy values.  The outer
        # snapshot encryption still protects the value at rest.
        return value, True


def _redact_json(value: Any, key: str | None = None) -> Any:
    if key and _SENSITIVE_KEY_RE.search(key):
        return "******" if value not in (None, "", [], {}) else value
    if isinstance(value, dict):
        return {str(item_key): _redact_json(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    return value


def redact_configuration_resource(domain: str, resource: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a safe resource view, including domain-specific redaction rules."""

    redacted = _redact_json(resource)
    if not isinstance(redacted, dict):
        return {}
    if domain == "environment":
        raw_variables = resource.get("variables")
        redacted_variables = redacted.get("variables")
        if isinstance(raw_variables, list) and isinstance(redacted_variables, list):
            safe_variables: list[Any] = []
            for index, raw_variable in enumerate(raw_variables):
                safe_variable = redacted_variables[index] if index < len(redacted_variables) else {}
                safe_item = dict(safe_variable) if isinstance(safe_variable, dict) else {}
                safe_item.pop("stored_ciphertext", None)
                if isinstance(raw_variable, dict):
                    variable_key = raw_variable.get("key")
                    if (
                        raw_variable.get("is_secret")
                        or isinstance(variable_key, str)
                        and _SENSITIVE_KEY_RE.search(variable_key)
                    ):
                        safe_item["value"] = "******" if raw_variable.get("value") else raw_variable.get("value")
                safe_variables.append(safe_item)
            redacted["variables"] = safe_variables
    elif domain == "global_variable":
        redacted.pop("stored_ciphertext", None)
        variable_key = resource.get("key")
        if resource.get("is_secret") or isinstance(variable_key, str) and _SENSITIVE_KEY_RE.search(variable_key):
            redacted["value"] = "******" if resource.get("value") else resource.get("value")
    elif domain == "performance_node":
        labels = resource.get("labels")
        capabilities = resource.get("capabilities")
        egress_allowlist = resource.get("egress_allowlist")
        redacted["labels"] = {"count": len(labels)} if isinstance(labels, dict) else {}
        redacted["capabilities"] = {"executors": sorted(_safe_executor_names(capabilities))}
        redacted["egress_allowlist"] = {"count": len(egress_allowlist)} if isinstance(egress_allowlist, list) else {}
    return redacted


def _wrap_payload(domain: str, resource_id: int, resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "domain": domain,
        "resource_id": resource_id,
        "resource": resource,
    }


def _finish_snapshot(
    domain: str,
    resource_id: int,
    project_id: int | None,
    resource_name: str,
    resource: dict[str, Any],
    redacted_resource: dict[str, Any],
) -> ConfigurationSnapshot:
    payload = _wrap_payload(domain, resource_id, _clone_json(resource))
    redacted_payload = _wrap_payload(domain, resource_id, _clone_json(redacted_resource))
    payload_json = _canonical_json(payload)
    return ConfigurationSnapshot(
        domain=domain,
        resource_id=resource_id,
        project_id=project_id,
        resource_name=resource_name,
        payload=payload,
        redacted_payload=redacted_payload,
        fingerprint=_fingerprint(payload_json),
        payload_encrypted=encrypt(payload_json),
    )


async def _assert_snapshot_access(
    db: AsyncSession,
    user: User,
    domain: str,
    project_id: int | None,
    *,
    require_write: bool = True,
) -> None:
    if domain == "ai_llm" or domain == "storage_policy":
        if user.role != UserRole.admin:
            raise ConfigurationSnapshotForbidden("只有管理员可以创建此配置版本")
        return
    if domain == "global_variable" and project_id is None:
        if user.role != UserRole.admin:
            raise ConfigurationSnapshotForbidden("只有管理员可以创建全局变量版本")
        return
    if domain == "performance_node":
        if user.role not in {UserRole.admin, UserRole.engineer}:
            raise ConfigurationSnapshotForbidden("只有管理员或工程师可以创建性能节点版本")
        return
    if domain == "notification":
        required_role = ProjectRole.owner if require_write else ProjectRole.viewer
    else:
        required_role = ProjectRole.editor if require_write else ProjectRole.viewer
    if project_id is None:
        raise ConfigurationSnapshotForbidden("配置资源缺少项目范围")
    await assert_project_access(db, user, project_id, required_role)


async def _environment_snapshot(
    db: AsyncSession, user: User, resource_id: int, *, require_write: bool = True
) -> ConfigurationSnapshot:
    environment = await db.get(Environment, resource_id)
    if environment is None:
        raise ConfigurationSnapshotNotFound("环境不存在")
    await _assert_snapshot_access(db, user, "environment", environment.project_id, require_write=require_write)
    variables = (
        (
            await db.execute(
                select(EnvVariable).where(EnvVariable.env_id == environment.id).order_by(EnvVariable.key.asc())
            )
        )
        .scalars()
        .all()
    )
    raw_variables: list[dict[str, Any]] = []
    for variable in variables:
        if variable.is_secret:
            value, stored_ciphertext = _decrypt_or_keep(variable.value)
        else:
            value, stored_ciphertext = (variable.value or "", False)
        raw_item: dict[str, Any] = {"key": variable.key, "value": value, "is_secret": bool(variable.is_secret)}
        if stored_ciphertext:
            raw_item["stored_ciphertext"] = True
        raw_variables.append(raw_item)
    resource = {
        "name": environment.name,
        "description": environment.description,
        "project_id": environment.project_id,
        "variables": raw_variables,
    }
    redacted_resource = redact_configuration_resource("environment", resource)
    return _finish_snapshot(
        "environment",
        environment.id,
        environment.project_id,
        environment.name,
        resource,
        redacted_resource,
    )


async def _global_variable_snapshot(
    db: AsyncSession, user: User, resource_id: int, *, require_write: bool = True
) -> ConfigurationSnapshot:
    variable = await db.get(GlobalVariable, resource_id)
    if variable is None:
        raise ConfigurationSnapshotNotFound("变量不存在")
    await _assert_snapshot_access(db, user, "global_variable", variable.project_id, require_write=require_write)
    value, stored_ciphertext = _decrypt_or_keep(variable.value_encrypted)
    resource: dict[str, Any] = {
        "scope_type": _enum_value(variable.scope_type),
        "project_id": variable.project_id,
        "key": variable.key,
        "value": value,
        "is_secret": bool(variable.is_secret),
        "description": variable.description,
    }
    if stored_ciphertext:
        resource["stored_ciphertext"] = True
    redacted_resource = redact_configuration_resource("global_variable", resource)
    return _finish_snapshot(
        "global_variable",
        variable.id,
        variable.project_id,
        variable.key,
        resource,
        redacted_resource,
    )


async def _ai_snapshot(
    db: AsyncSession, user: User, resource_id: int, *, require_write: bool = True
) -> ConfigurationSnapshot:
    config = await db.get(AILLMConfig, resource_id)
    if config is None:
        raise ConfigurationSnapshotNotFound("AI 配置不存在")
    await _assert_snapshot_access(db, user, "ai_llm", None)
    api_key, stored_ciphertext = _decrypt_or_keep(config.api_key_encrypted)
    resource: dict[str, Any] = {
        "name": config.name,
        "provider": config.provider,
        "api_key": api_key,
        "endpoint": config.endpoint,
        "model_name": config.model_name,
        "default_params": _clone_json(config.default_params or {}),
        "enabled": bool(config.enabled),
        "supports_vision": bool(config.supports_vision),
        "description": config.description,
    }
    if stored_ciphertext:
        resource["api_key_stored_ciphertext"] = True
    redacted_resource = redact_configuration_resource("ai_llm", resource)
    return _finish_snapshot("ai_llm", config.id, None, config.name, resource, redacted_resource)


async def _storage_snapshot(
    db: AsyncSession, user: User, resource_id: int, *, require_write: bool = True
) -> ConfigurationSnapshot:
    policy = await db.get(StoragePolicy, resource_id)
    if policy is None:
        raise ConfigurationSnapshotNotFound("存储策略不存在")
    await _assert_snapshot_access(db, user, "storage_policy", None)
    resource = {
        "name": policy.name,
        "prefix": policy.prefix,
        "retention_days": policy.retention_days,
        "max_size_gb": policy.max_size_gb,
        "enabled": bool(policy.enabled),
        "description": policy.description,
    }
    return _finish_snapshot(
        "storage_policy",
        policy.id,
        None,
        policy.name,
        resource,
        redact_configuration_resource("storage_policy", resource),
    )


async def _notification_snapshot(
    db: AsyncSession, user: User, resource_id: int, *, require_write: bool = True
) -> ConfigurationSnapshot:
    config = await db.get(NotificationConfig, resource_id)
    if config is None:
        raise ConfigurationSnapshotNotFound("通知配置不存在")
    await _assert_snapshot_access(db, user, "notification", config.project_id, require_write=require_write)
    raw_config = decrypt_config(config.config or {})
    resource = {
        "name": config.name,
        "project_id": config.project_id,
        "channel": _enum_value(config.channel),
        "is_enabled": bool(config.is_enabled),
        "config": _clone_json(raw_config),
    }
    return _finish_snapshot(
        "notification",
        config.id,
        config.project_id,
        config.name,
        resource,
        redact_configuration_resource("notification", resource),
    )


async def _performance_node_snapshot(
    db: AsyncSession, user: User, resource_id: int, *, require_write: bool = True
) -> ConfigurationSnapshot:
    node = await db.get(PerformanceNode, resource_id)
    if node is None:
        raise ConfigurationSnapshotNotFound("性能节点不存在")
    await _assert_snapshot_access(db, user, "performance_node", None)
    resource = {
        "node_id": node.node_id,
        "name": node.name,
        "queue_name": node.queue_name,
        "enabled": bool(node.enabled),
        "labels": _clone_json(node.labels or {}),
        "capabilities": _clone_json(node.capabilities or {}),
        "max_vus": node.max_vus,
        "max_concurrency": node.max_concurrency,
        "egress_allowlist": _clone_json(node.egress_allowlist or []),
    }
    redacted_resource = redact_configuration_resource("performance_node", resource)
    return _finish_snapshot("performance_node", node.id, None, node.name, resource, redacted_resource)


def _safe_executor_names(capabilities: Any) -> list[str]:
    if not isinstance(capabilities, dict):
        return []
    raw = capabilities.get("executors")
    if not isinstance(raw, (list, tuple, set)):
        return []
    return sorted({item.strip() for item in raw if isinstance(item, str) and item.strip()})


async def load_configuration_snapshot(
    db: AsyncSession,
    user: User,
    domain: str,
    resource_id: int,
    *,
    require_write: bool = True,
) -> ConfigurationSnapshot:
    if domain not in SUPPORTED_SNAPSHOT_DOMAINS:
        raise ConfigurationSnapshotUnsupported("该配置域不支持版本快照")
    loaders = {
        "environment": _environment_snapshot,
        "global_variable": _global_variable_snapshot,
        "ai_llm": _ai_snapshot,
        "storage_policy": _storage_snapshot,
        "notification": _notification_snapshot,
        "performance_node": _performance_node_snapshot,
    }
    try:
        return await loaders[domain](db, user, resource_id, require_write=require_write)
    except ConfigurationSnapshotError:
        raise
