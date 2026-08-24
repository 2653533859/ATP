"""Build safe field-level diffs between a configuration revision and its resource."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.models.configuration_revision import ConfigurationRevision
from app.models.user import User
from app.services.configuration_snapshots import (
    ConfigurationSnapshotNotFound,
    _SENSITIVE_KEY_RE,
    _canonical_json,
    _fingerprint,
    load_configuration_snapshot,
    redact_configuration_resource,
)


MAX_DIFF_FIELDS = 500
_MISSING = object()


class ConfigurationRevisionDiffError(Exception):
    """Base error for an invalid or unreadable historical revision."""


class ConfigurationRevisionIntegrityError(ConfigurationRevisionDiffError):
    pass


@dataclass(frozen=True)
class ConfigurationRevisionDiff:
    revision_id: int
    domain: str
    resource_id: int
    project_id: int | None
    resource_name: str
    historical_fingerprint: str
    current_fingerprint: str | None
    current_available: bool
    current_status: str
    changed: bool
    changed_field_count: int
    sensitive_changed_field_count: int
    truncated: bool
    message: str | None
    changes: list[dict[str, Any]]
    impacts: list[dict[str, Any]]


_IMPACT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "environment": {
        "code": "environment_execution",
        "title": "环境变量变更会影响测试执行",
        "description": "环境变量可能改变接口、Web、Android 和性能用例的目标地址、认证信息或参数注入。",
        "severity": "high",
        "affected_features": ["接口测试", "Web UI 自动化", "Android 自动化", "性能测试"],
    },
    "global_variable": {
        "code": "global_variable_consumers",
        "title": "全局变量变更会影响引用方",
        "description": "引用该变量的用例、脚本、套件和场景可能得到不同的运行输入。",
        "severity": "high",
        "affected_features": ["用例执行", "脚本", "测试套件", "测试计划"],
    },
    "ai_llm": {
        "code": "ai_generation_and_diagnosis",
        "title": "AI 配置变更会影响智能能力",
        "description": "模型、Endpoint、参数或能力开关变化可能影响用例、数据集、Mock 生成和失败诊断。",
        "severity": "high",
        "affected_features": ["AI 用例生成", "测试数据生成", "Mock 生成", "失败诊断"],
    },
    "storage_policy": {
        "code": "artifact_retention",
        "title": "存储策略变更会影响测试产物",
        "description": "保留周期、容量或前缀变化可能影响截图、报告、APK 和脚本等对象的写入与清理。",
        "severity": "medium",
        "affected_features": ["截图", "测试报告", "APK 资产", "脚本产物"],
    },
    "notification": {
        "code": "notification_delivery",
        "title": "通知配置变更会影响消息投递",
        "description": "渠道、启用状态或投递配置变化可能影响执行完成、失败和告警通知。",
        "severity": "high",
        "affected_features": ["执行通知", "失败告警", "测试报告通知"],
    },
    "performance_node": {
        "code": "performance_scheduling",
        "title": "性能节点变更会影响压测调度",
        "description": "队列、执行器能力、并发容量或出口限制变化可能影响性能任务的调度和运行规模。",
        "severity": "medium",
        "affected_features": ["性能任务调度", "并发容量", "执行器能力", "目标出口"],
    },
}


def _copy_json(value: Any) -> Any:
    if value is _MISSING:
        return None
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _path_for_key(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _path_for_index(path: str, index: int) -> str:
    return f"{path}[{index}]"


def _collect_sensitive_paths(raw: Any, safe: Any, path: str, paths: set[str]) -> None:
    """Find paths masked by key policy or by domain-specific redaction."""

    if raw is _MISSING:
        return
    if isinstance(raw, dict):
        safe_dict = safe if isinstance(safe, dict) else {}
        if raw.get("is_secret") is True and "value" in raw:
            paths.add(_path_for_key(path, "value"))
        if isinstance(raw.get("key"), str) and _SENSITIVE_KEY_RE.search(raw["key"]) and "value" in raw:
            paths.add(_path_for_key(path, "value"))
        for key, raw_value in raw.items():
            key_text = str(key)
            child_path = _path_for_key(path, key_text)
            safe_value = safe_dict.get(key, _MISSING)
            if _SENSITIVE_KEY_RE.search(key_text) or raw_value != safe_value:
                paths.add(child_path)
            _collect_sensitive_paths(raw_value, safe_value, child_path, paths)
        return
    if isinstance(raw, list):
        safe_list = safe if isinstance(safe, list) else []
        for index, raw_value in enumerate(raw):
            safe_value = safe_list[index] if index < len(safe_list) else _MISSING
            _collect_sensitive_paths(raw_value, safe_value, _path_for_index(path, index), paths)


def _is_sensitive_path(path: str, sensitive_paths: set[str]) -> bool:
    return any(
        path == sensitive_path
        or path.startswith(f"{sensitive_path}.")
        or sensitive_path.startswith(f"{path}.")
        or sensitive_path.startswith(f"{path}[")
        for sensitive_path in sensitive_paths
    )


def _append_change(
    changes: list[dict[str, Any]],
    *,
    path: str,
    change_type: str,
    before: Any,
    after: Any,
    before_safe: Any,
    after_safe: Any,
    sensitive_paths: set[str],
) -> None:
    sensitive = _is_sensitive_path(path, sensitive_paths)
    changes.append(
        {
            "path": path,
            "change_type": change_type,
            "changed": True,
            "sensitive": sensitive,
            "before": None if sensitive else _copy_json(before_safe),
            "after": None if sensitive else _copy_json(after_safe),
        }
    )


def _walk_diff(
    before: Any,
    after: Any,
    before_safe: Any,
    after_safe: Any,
    path: str,
    sensitive_paths: set[str],
    changes: list[dict[str, Any]],
) -> bool:
    if len(changes) >= MAX_DIFF_FIELDS:
        return True
    if before is _MISSING:
        _append_change(
            changes,
            path=path,
            change_type="added",
            before=before,
            after=after,
            before_safe=before_safe,
            after_safe=after_safe,
            sensitive_paths=sensitive_paths,
        )
        return len(changes) >= MAX_DIFF_FIELDS
    if after is _MISSING:
        _append_change(
            changes,
            path=path,
            change_type="removed",
            before=before,
            after=after,
            before_safe=before_safe,
            after_safe=after_safe,
            sensitive_paths=sensitive_paths,
        )
        return len(changes) >= MAX_DIFF_FIELDS
    if isinstance(before, dict) and isinstance(after, dict):
        before_safe_dict = before_safe if isinstance(before_safe, dict) else {}
        after_safe_dict = after_safe if isinstance(after_safe, dict) else {}
        for key in sorted(set(before) | set(after), key=str):
            key_text = str(key)
            _walk_diff(
                before.get(key, _MISSING),
                after.get(key, _MISSING),
                before_safe_dict.get(key, _MISSING),
                after_safe_dict.get(key, _MISSING),
                _path_for_key(path, key_text),
                sensitive_paths,
                changes,
            )
            if len(changes) >= MAX_DIFF_FIELDS:
                return True
        return False
    if isinstance(before, list) and isinstance(after, list):
        before_safe_list = before_safe if isinstance(before_safe, list) else []
        after_safe_list = after_safe if isinstance(after_safe, list) else []
        for index in range(max(len(before), len(after))):
            _walk_diff(
                before[index] if index < len(before) else _MISSING,
                after[index] if index < len(after) else _MISSING,
                before_safe_list[index] if index < len(before_safe_list) else _MISSING,
                after_safe_list[index] if index < len(after_safe_list) else _MISSING,
                _path_for_index(path, index),
                sensitive_paths,
                changes,
            )
            if len(changes) >= MAX_DIFF_FIELDS:
                return True
        return False
    if before != after:
        _append_change(
            changes,
            path=path,
            change_type="changed",
            before=before,
            after=after,
            before_safe=before_safe,
            after_safe=after_safe,
            sensitive_paths=sensitive_paths,
        )
    return False


def decode_configuration_revision_payload(revision: ConfigurationRevision) -> dict[str, Any]:
    try:
        payload = json.loads(decrypt(revision.payload_encrypted))
    except Exception as exc:
        raise ConfigurationRevisionIntegrityError("历史配置版本无法解密") from exc
    if not isinstance(payload, dict):
        raise ConfigurationRevisionIntegrityError("历史配置版本格式无效")
    if payload.get("domain") != revision.domain or payload.get("resource_id") != revision.resource_id:
        raise ConfigurationRevisionIntegrityError("历史配置版本与资源不匹配")
    if _fingerprint(_canonical_json(payload)) != revision.fingerprint:
        raise ConfigurationRevisionIntegrityError("历史配置版本校验失败")
    return payload


# Kept as a private alias for callers that imported the helper while the diff
# endpoint was being developed.  New write paths use the explicit public name.
_decode_revision_payload = decode_configuration_revision_payload


def _impact_for(domain: str, *, current_available: bool, changed: bool) -> list[dict[str, Any]]:
    if not changed and current_available:
        return []
    definition = _IMPACT_DEFINITIONS.get(domain)
    if definition is None:
        return []
    impact = dict(definition)
    if not current_available:
        impact["description"] = "当前配置资源已不存在，无法计算字段差异；" + str(impact["description"])
    return [impact]


async def build_configuration_revision_diff(
    db: AsyncSession,
    user: User,
    revision: ConfigurationRevision,
) -> ConfigurationRevisionDiff:
    historical_payload = decode_configuration_revision_payload(revision)

    try:
        current = await load_configuration_snapshot(
            db,
            user,
            revision.domain,
            revision.resource_id,
            require_write=False,
        )
    except ConfigurationSnapshotNotFound:
        return ConfigurationRevisionDiff(
            revision_id=revision.id,
            domain=revision.domain,
            resource_id=revision.resource_id,
            project_id=revision.project_id,
            resource_name=revision.resource_name,
            historical_fingerprint=revision.fingerprint,
            current_fingerprint=None,
            current_available=False,
            current_status="missing",
            changed=True,
            changed_field_count=0,
            sensitive_changed_field_count=0,
            truncated=False,
            message="当前配置资源已不存在，无法计算字段差异",
            changes=[],
            impacts=_impact_for(revision.domain, current_available=False, changed=True),
        )

    historical_resource = historical_payload.get("resource", {})
    current_resource = current.payload.get("resource", {})
    historical_safe_resource = redact_configuration_resource(revision.domain, historical_resource)
    current_safe_resource = current.redacted_payload.get("resource", {})
    if not isinstance(historical_resource, dict) or not isinstance(current_resource, dict):
        raise ConfigurationRevisionIntegrityError("配置版本资源数据无效")
    if not isinstance(historical_safe_resource, dict) or not isinstance(current_safe_resource, dict):
        raise ConfigurationRevisionIntegrityError("配置版本脱敏资源数据无效")

    sensitive_paths: set[str] = set()
    _collect_sensitive_paths(historical_resource, historical_safe_resource, "resource", sensitive_paths)
    _collect_sensitive_paths(current_resource, current_safe_resource, "resource", sensitive_paths)
    changes: list[dict[str, Any]] = []
    truncated = _walk_diff(
        historical_resource,
        current_resource,
        historical_safe_resource,
        current_safe_resource,
        "resource",
        sensitive_paths,
        changes,
    )
    sensitive_changed_count = sum(1 for change in changes if change["sensitive"])
    changed = bool(changes) or current.fingerprint != revision.fingerprint
    return ConfigurationRevisionDiff(
        revision_id=revision.id,
        domain=revision.domain,
        resource_id=revision.resource_id,
        project_id=revision.project_id,
        resource_name=revision.resource_name,
        historical_fingerprint=revision.fingerprint,
        current_fingerprint=current.fingerprint,
        current_available=True,
        current_status="available",
        changed=changed,
        changed_field_count=len(changes),
        sensitive_changed_field_count=sensitive_changed_count,
        truncated=truncated,
        message=None,
        changes=changes,
        impacts=_impact_for(revision.domain, current_available=True, changed=changed),
    )
