"""Transactional restoration of one encrypted configuration revision."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt, encrypt_config
from app.models.ai_llm_config import AILLMConfig
from app.models.configuration_revision import ConfigurationRevision
from app.models.environment import Environment, EnvVariable
from app.models.global_variable import GlobalVariable, ScopeType
from app.models.notification import NotificationConfig, NotifyChannel
from app.models.performance_node import PerformanceNode
from app.models.storage_policy import StoragePolicy
from app.models.user import User
from app.services.configuration_diffs import (
    ConfigurationRevisionIntegrityError,
    decode_configuration_revision_payload,
)
from app.services.configuration_snapshots import (
    ConfigurationSnapshotNotFound,
    ConfigurationSnapshotUnsupported,
    load_configuration_snapshot,
)


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigurationRollbackError(Exception):
    """Base error for an invalid or unsafe rollback request."""


class ConfigurationRollbackConflict(ConfigurationRollbackError):
    pass


@dataclass(frozen=True)
class ConfigurationRollbackResult:
    source_revision_id: int
    resource_id: int
    domain: str
    changed: bool
    message: str
    revision: ConfigurationRevision


def _resource(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("resource")
    if not isinstance(value, dict):
        raise ConfigurationRevisionIntegrityError("历史配置版本资源数据无效")
    return value


def _text(resource: dict[str, Any], key: str, *, required: bool = True, max_length: int | None = None) -> str | None:
    value = resource.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise ConfigurationRevisionIntegrityError(f"历史配置版本字段无效: {key}")
    if max_length is not None and len(value) > max_length:
        raise ConfigurationRevisionIntegrityError(f"历史配置版本字段过长: {key}")
    return value


def _bool(resource: dict[str, Any], key: str) -> bool:
    value = resource.get(key)
    if not isinstance(value, bool):
        raise ConfigurationRevisionIntegrityError(f"历史配置版本字段无效: {key}")
    return value


def _int_or_none(resource: dict[str, Any], key: str) -> int | None:
    value = resource.get(key)
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
        raise ConfigurationRevisionIntegrityError(f"历史配置版本字段无效: {key}")
    return value


def _dict(resource: dict[str, Any], key: str) -> dict[str, Any]:
    value = resource.get(key)
    if not isinstance(value, dict):
        raise ConfigurationRevisionIntegrityError(f"历史配置版本字段无效: {key}")
    return value


def _string_list(resource: dict[str, Any], key: str) -> list[str]:
    value = resource.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigurationRevisionIntegrityError(f"历史配置版本字段无效: {key}")
    return value


def _encrypted_value(resource: dict[str, Any], key: str) -> str:
    value = resource.get(key)
    if not isinstance(value, str):
        raise ConfigurationRevisionIntegrityError(f"历史配置版本字段无效: {key}")
    marker = "stored_ciphertext" if key == "value" else f"{key}_stored_ciphertext"
    return value if resource.get(marker) else encrypt(value) if value else ""


def _validate_revision_target(revision: ConfigurationRevision, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("domain") != revision.domain or payload.get("resource_id") != revision.resource_id:
        raise ConfigurationRevisionIntegrityError("历史配置版本与资源不匹配")
    return _resource(payload)


async def _restore_environment(db: AsyncSession, item: Environment, resource: dict[str, Any]) -> None:
    project_id = _historical_project_id_from_resource(resource)
    if project_id != item.project_id:
        raise ConfigurationRollbackConflict("环境所属项目已变化，不能回滚")
    name = _text(resource, "name", max_length=64)
    description = _text(resource, "description", required=False)
    variables = resource.get("variables")
    if not isinstance(variables, list) or len(variables) > 200:
        raise ConfigurationRevisionIntegrityError("历史配置版本环境变量数据无效")
    normalized: dict[str, tuple[str, bool, bool]] = {}
    for variable in variables:
        if not isinstance(variable, dict):
            raise ConfigurationRevisionIntegrityError("历史配置版本环境变量数据无效")
        key = variable.get("key")
        value = variable.get("value", "")
        is_secret = variable.get("is_secret")
        if (
            not isinstance(key, str)
            or not _ENV_KEY_RE.fullmatch(key)
            or not isinstance(value, str)
            or not isinstance(is_secret, bool)
            or key in normalized
        ):
            raise ConfigurationRevisionIntegrityError("历史配置版本环境变量字段无效")
        normalized[key] = (value, is_secret, bool(variable.get("stored_ciphertext")))
    existing = (
        (await db.execute(select(EnvVariable).where(EnvVariable.env_id == item.id).with_for_update())).scalars().all()
    )
    existing_by_key = {variable.key: variable for variable in existing}
    item.name = name or item.name
    item.description = description
    for key, (value, is_secret, stored_ciphertext) in normalized.items():
        variable = existing_by_key.pop(key, None)
        if variable is None:
            variable = EnvVariable(env_id=item.id, key=key)
            db.add(variable)
        variable.value = value if stored_ciphertext or not is_secret else encrypt(value) if value else ""
        variable.is_secret = is_secret
    for variable in existing_by_key.values():
        await db.delete(variable)


def _historical_project_id_from_resource(resource: dict[str, Any]) -> int:
    value = resource.get("project_id")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigurationRevisionIntegrityError("历史配置版本项目范围无效")
    return value


async def _restore_global_variable(db: AsyncSession, item: GlobalVariable, resource: dict[str, Any]) -> None:
    project_id = resource.get("project_id")
    if project_id is not None and (isinstance(project_id, bool) or not isinstance(project_id, int) or project_id < 1):
        raise ConfigurationRevisionIntegrityError("历史配置版本项目范围无效")
    if project_id != item.project_id:
        raise ConfigurationRollbackConflict("变量所属项目已变化，不能回滚")
    scope_value = _text(resource, "scope_type")
    try:
        scope_type = ScopeType(scope_value)
    except ValueError as exc:
        raise ConfigurationRevisionIntegrityError("历史配置版本变量作用域无效") from exc
    if (scope_type == ScopeType.global_scope) != (item.project_id is None):
        raise ConfigurationRollbackConflict("变量作用域已变化，不能回滚")
    item.scope_type = scope_type
    item.key = _text(resource, "key", max_length=256) or item.key
    item.value_encrypted = _encrypted_value(resource, "value")
    item.is_secret = _bool(resource, "is_secret")
    item.description = _text(resource, "description", required=False)


async def _restore_ai(db: AsyncSession, item: AILLMConfig, resource: dict[str, Any]) -> None:
    item.name = _text(resource, "name", max_length=64) or item.name
    item.provider = _text(resource, "provider", max_length=32) or item.provider
    item.api_key_encrypted = _encrypted_value(resource, "api_key")
    item.endpoint = _text(resource, "endpoint", required=False, max_length=256)
    item.model_name = _text(resource, "model_name", max_length=64) or item.model_name
    item.default_params = _dict(resource, "default_params")
    item.enabled = _bool(resource, "enabled")
    item.supports_vision = _bool(resource, "supports_vision")
    item.description = _text(resource, "description", required=False)


async def _restore_storage(db: AsyncSession, item: StoragePolicy, resource: dict[str, Any]) -> None:
    item.name = _text(resource, "name", max_length=64) or item.name
    item.prefix = _text(resource, "prefix", max_length=128) or item.prefix
    retention_days = _int_or_none(resource, "retention_days")
    if retention_days is None:
        raise ConfigurationRevisionIntegrityError("历史配置版本保留天数无效")
    item.retention_days = retention_days
    item.max_size_gb = resource.get("max_size_gb")
    if item.max_size_gb is not None and (
        isinstance(item.max_size_gb, bool) or not isinstance(item.max_size_gb, (int, float)) or item.max_size_gb < 0
    ):
        raise ConfigurationRevisionIntegrityError("历史配置版本存储容量无效")
    item.enabled = _bool(resource, "enabled")
    item.description = _text(resource, "description", required=False)


async def _restore_notification(db: AsyncSession, item: NotificationConfig, resource: dict[str, Any]) -> None:
    project_id = _historical_project_id_from_resource(resource)
    if project_id != item.project_id:
        raise ConfigurationRollbackConflict("通知配置所属项目已变化，不能回滚")
    try:
        channel = NotifyChannel(_text(resource, "channel"))
    except ValueError as exc:
        raise ConfigurationRevisionIntegrityError("历史配置版本通知渠道无效") from exc
    item.name = _text(resource, "name", max_length=128) or item.name
    item.channel = channel
    item.is_enabled = _bool(resource, "is_enabled")
    item.config = encrypt_config(_dict(resource, "config"))


async def _restore_performance_node(db: AsyncSession, item: PerformanceNode, resource: dict[str, Any]) -> None:
    node_id = _text(resource, "node_id", max_length=128)
    if node_id is None or not _IDENTIFIER_RE.fullmatch(node_id):
        raise ConfigurationRevisionIntegrityError("历史配置版本性能节点 ID 无效")
    item.node_id = node_id
    item.name = _text(resource, "name", max_length=128) or item.name
    item.queue_name = _text(resource, "queue_name", max_length=128) or item.queue_name
    item.enabled = _bool(resource, "enabled")
    item.labels = _dict(resource, "labels")
    item.capabilities = _dict(resource, "capabilities")
    item.max_vus = _int_or_none(resource, "max_vus")
    item.max_concurrency = _int_or_none(resource, "max_concurrency")
    item.egress_allowlist = _string_list(resource, "egress_allowlist")
    if not item.enabled:
        item.status = "disabled"


async def rollback_configuration_revision(
    db: AsyncSession,
    user: User,
    revision: ConfigurationRevision,
) -> ConfigurationRollbackResult:
    """Restore one resource without committing until the caller writes audit data."""

    if revision.domain not in {
        "environment",
        "global_variable",
        "ai_llm",
        "storage_policy",
        "notification",
        "performance_node",
    }:
        raise ConfigurationSnapshotUnsupported("该配置域不支持回滚")
    payload = decode_configuration_revision_payload(revision)
    resource = _validate_revision_target(revision, payload)
    loaders = {
        "environment": (Environment, _restore_environment),
        "global_variable": (GlobalVariable, _restore_global_variable),
        "ai_llm": (AILLMConfig, _restore_ai),
        "storage_policy": (StoragePolicy, _restore_storage),
        "notification": (NotificationConfig, _restore_notification),
        "performance_node": (PerformanceNode, _restore_performance_node),
    }
    model, restore = loaders[revision.domain]
    item = await db.get(model, revision.resource_id, with_for_update=True)
    if item is None:
        raise ConfigurationSnapshotNotFound("当前配置资源不存在")
    current = await load_configuration_snapshot(db, user, revision.domain, revision.resource_id, require_write=True)
    if current.project_id != revision.project_id:
        raise ConfigurationRollbackConflict("配置版本项目范围与当前资源不一致，不能回滚")
    if revision.domain in {"environment", "notification"}:
        _historical_project_id_from_resource(resource)
    elif revision.domain == "global_variable":
        if resource.get("project_id") != current.project_id:
            raise ConfigurationRollbackConflict("变量所属项目已变化，不能回滚")
    if current.fingerprint == revision.fingerprint:
        return ConfigurationRollbackResult(
            source_revision_id=revision.id,
            resource_id=revision.resource_id,
            domain=revision.domain,
            changed=False,
            message="当前配置已是目标版本，无需恢复",
            revision=revision,
        )

    await cast(Any, restore)(db, item, resource)
    await db.flush()
    restored = await load_configuration_snapshot(db, user, revision.domain, revision.resource_id, require_write=True)
    restored_revision = ConfigurationRevision(
        domain=restored.domain,
        resource_id=restored.resource_id,
        project_id=restored.project_id,
        resource_name=restored.resource_name,
        payload_encrypted=restored.payload_encrypted,
        redacted_payload=restored.redacted_payload,
        fingerprint=restored.fingerprint,
        reason="配置回滚",
        created_by=user.id,
    )
    db.add(restored_revision)
    await db.flush()
    return ConfigurationRollbackResult(
        source_revision_id=revision.id,
        resource_id=revision.resource_id,
        domain=revision.domain,
        changed=True,
        message="配置已恢复，并创建新的回滚版本",
        revision=restored_revision,
    )
