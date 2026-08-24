"""Safe, read-only aggregation for the system configuration center.

The configuration center is an index, not a second write API.  Existing resource
APIs remain the source of truth for edits and permissions.  This endpoint only
returns metadata and deliberately avoids decrypting any secret value.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_project_role, require_engineer
from app.core.config import settings
from app.core.database import get_db
from app.models.ai_llm_config import AILLMConfig
from app.models.configuration_revision import ConfigurationRevision
from app.models.environment import Environment, EnvVariable
from app.models.global_variable import GlobalVariable, ScopeType
from app.models.notification import NotificationConfig
from app.models.performance_node import PerformanceNode
from app.models.storage_policy import StoragePolicy
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, role_satisfies
from app.schemas.configuration_center import (
    ConfigurationCenterOverviewOut,
    ConfigurationEntryOut,
    ConfigurationRevisionCreateIn,
    ConfigurationRevisionOut,
    ConfigurationSectionOut,
)
from app.services.audit import write_audit_log
from app.services.configuration_snapshots import (
    ConfigurationSnapshotForbidden,
    ConfigurationSnapshotNotFound,
    ConfigurationSnapshotUnsupported,
    SUPPORTED_SNAPSHOT_DOMAINS,
    load_configuration_snapshot,
)
from app.services.project_scope import visible_project_ids

router = APIRouter(prefix="/configuration-center", tags=["配置中心"])


_SECTION_DEFINITIONS = (
    ("startup", "启动配置", "当前进程的安全启动档案；修改后需按部署方式重启", "/system/startup-config", False, True),
    ("environment", "项目环境", "项目执行时注入的环境和变量数量", "/system/environments", True, False),
    ("global_variable", "全局变量", "全局或项目范围的变量元数据", "/system/global-variables", True, False),
    ("ai_llm", "AI 模型", "模型供应商、启用状态和能力摘要", "/system/ai-llm-configs", False, False),
    ("storage_policy", "存储策略", "对象存储清理策略与保留规则", "/system/storage", False, False),
    ("notification", "通知配置", "项目通知渠道和启用状态", "/system/notifications", True, False),
    ("performance_node", "性能节点", "压测节点队列、状态和容量摘要", "/system/performance", False, False),
)


def _safe_text(value: Any, default: str = "") -> str:
    return str(value).strip() if value is not None else default


def _enum_value(value: Any) -> str:
    return _safe_text(getattr(value, "value", value), "unknown")


def _safe_executors(capabilities: Any) -> list[str]:
    """Only return executor names from arbitrary node capability JSON."""

    if not isinstance(capabilities, dict):
        return []
    raw = capabilities.get("executors")
    if not isinstance(raw, (list, tuple, set)):
        return []
    return sorted({item.strip() for item in raw if isinstance(item, str) and item.strip()})


def _startup_summary() -> dict[str, Any]:
    """Expose feature switches without exposing connection details or credentials."""

    queues = sorted(
        {
            item.strip()
            for item in _safe_text(settings.CELERY_QUEUES).split(",")
            if item.strip() and len(item.strip()) <= 64
        }
    )
    recorder_mode = _safe_text(settings.WEB_RECORDER_MODE, "local").lower() or "local"
    adb_mode = _safe_text(settings.ADB_SCAN_MODE, "local").lower() or "local"
    return {
        "app_env": _safe_text(settings.APP_ENV, "development"),
        "adb_scan_enabled": bool(settings.ADB_SCAN_ENABLED),
        "adb_scan_mode": adb_mode,
        "android_worker_enabled": bool(_safe_text(settings.ANDROID_WORKER_ID)),
        "performance_node_enabled": bool(settings.PERFORMANCE_NODE_ENABLED),
        "performance_metrics_enabled": bool(settings.PERFORMANCE_METRICS_ENABLED),
        "web_recorder_mode": recorder_mode,
        "worker_queues": queues,
        "mock_standalone_enabled": int(settings.MOCK_STANDALONE_PORT or 0) > 0,
        "ai_healing_enabled": bool(settings.AI_HEALING_ENABLED),
    }


async def _can_manage_project(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    required: ProjectRole,
    cache: dict[tuple[int, ProjectRole], bool],
) -> bool:
    if project_id is None:
        return False
    if user.role == UserRole.admin:
        return True
    key = (project_id, required)
    if key not in cache:
        role = await get_project_role(db, user, project_id)
        cache[key] = role is not None and role_satisfies(role, required)
    return cache[key]


def _entry(
    *,
    domain: str,
    resource_id: int | None,
    project_id: int | None,
    name: str,
    status: str,
    updated_at: datetime | None,
    summary: dict[str, Any],
    route: str,
    can_manage: bool = False,
) -> ConfigurationEntryOut:
    return ConfigurationEntryOut(
        domain=domain,
        resource_id=resource_id,
        project_id=project_id,
        name=name,
        status=status,
        updated_at=updated_at,
        summary=summary,
        route=route,
        can_manage=can_manage,
    )


def _section(
    key: str,
    title: str,
    description: str,
    route: str,
    project_scoped: bool,
    readonly: bool,
    entries: list[ConfigurationEntryOut],
    *,
    available: bool = True,
) -> ConfigurationSectionOut:
    entries.sort(key=lambda item: (item.project_id is not None, item.project_id or 0, item.name.lower()))
    return ConfigurationSectionOut(
        key=key,
        title=title,
        description=description,
        route=route,
        project_scoped=project_scoped,
        readonly=readonly,
        available=available,
        count=len(entries),
        entries=entries,
    )


async def _load_environment_entries(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    cache: dict[tuple[int, ProjectRole], bool],
) -> list[ConfigurationEntryOut]:
    query = select(Environment).where(Environment.project_id.in_(visible_project_ids(user)))
    if project_id is not None:
        query = query.where(Environment.project_id == project_id)
    environments = (await db.execute(query)).scalars().all()
    env_ids = [item.id for item in environments]
    variables_by_env: dict[int, list[EnvVariable]] = {env_id: [] for env_id in env_ids}
    if env_ids:
        variables = (await db.execute(select(EnvVariable).where(EnvVariable.env_id.in_(env_ids)))).scalars().all()
        for variable in variables:
            variables_by_env.setdefault(variable.env_id, []).append(variable)
    return [
        _entry(
            domain="environment",
            resource_id=environment.id,
            project_id=environment.project_id,
            name=environment.name,
            status="active",
            updated_at=environment.updated_at,
            summary={
                "variable_count": len(variables_by_env.get(environment.id, [])),
                "secret_count": sum(1 for item in variables_by_env.get(environment.id, []) if item.is_secret),
            },
            route=f"/system/environments?project_id={environment.project_id}",
            can_manage=await _can_manage_project(db, user, environment.project_id, ProjectRole.editor, cache),
        )
        for environment in environments
    ]


async def _load_global_variable_entries(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    cache: dict[tuple[int, ProjectRole], bool],
) -> list[ConfigurationEntryOut]:
    query = select(GlobalVariable).where(
        or_(
            GlobalVariable.scope_type == ScopeType.global_scope,
            GlobalVariable.project_id.in_(visible_project_ids(user)),
        )
    )
    if project_id is not None:
        query = query.where(
            or_(
                GlobalVariable.scope_type == ScopeType.global_scope,
                GlobalVariable.project_id == project_id,
            )
        )
    variables = (await db.execute(query)).scalars().all()
    return [
        _entry(
            domain="global_variable",
            resource_id=variable.id,
            project_id=variable.project_id,
            name=variable.key,
            status="secret" if variable.is_secret else "active",
            updated_at=variable.updated_at,
            summary={
                "scope_type": _enum_value(variable.scope_type),
                "is_secret": bool(variable.is_secret),
                "has_value": bool(variable.value_encrypted),
            },
            route=(
                f"/system/global-variables?project_id={variable.project_id}"
                if variable.project_id is not None
                else "/system/global-variables"
            ),
            can_manage=(
                await _can_manage_project(db, user, variable.project_id, ProjectRole.editor, cache)
                if variable.project_id is not None
                else user.role == UserRole.admin
            ),
        )
        for variable in variables
    ]


async def _load_notification_entries(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    cache: dict[tuple[int, ProjectRole], bool],
) -> list[ConfigurationEntryOut]:
    query = select(NotificationConfig).where(NotificationConfig.project_id.in_(visible_project_ids(user)))
    if project_id is not None:
        query = query.where(NotificationConfig.project_id == project_id)
    configs = (await db.execute(query)).scalars().all()
    return [
        _entry(
            domain="notification",
            resource_id=config.id,
            project_id=config.project_id,
            name=config.name,
            status="enabled" if config.is_enabled else "disabled",
            updated_at=config.updated_at,
            summary={"channel": _enum_value(config.channel), "is_enabled": bool(config.is_enabled)},
            route=f"/system/notifications?project_id={config.project_id}",
            can_manage=await _can_manage_project(db, user, config.project_id, ProjectRole.owner, cache),
        )
        for config in configs
    ]


@router.get("/overview", response_model=ConfigurationCenterOverviewOut)
async def get_configuration_center_overview(
    project_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
) -> ConfigurationCenterOverviewOut:
    """Return only configuration metadata visible to the current engineer."""

    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)

    now = datetime.now(timezone.utc)
    role_cache: dict[tuple[int, ProjectRole], bool] = {}
    sections: list[ConfigurationSectionOut] = []

    startup_entry = _entry(
        domain="startup",
        resource_id=None,
        project_id=None,
        name="当前进程启动档案",
        status="active",
        updated_at=None,
        summary=_startup_summary(),
        route="/system/startup-config",
    )
    sections.append(_section(*_SECTION_DEFINITIONS[0], [startup_entry]))

    sections.append(
        _section(
            *_SECTION_DEFINITIONS[1],
            await _load_environment_entries(db, user, project_id, role_cache),
        )
    )
    sections.append(
        _section(
            *_SECTION_DEFINITIONS[2],
            await _load_global_variable_entries(db, user, project_id, role_cache),
        )
    )

    is_admin = user.role == UserRole.admin
    ai_entries: list[ConfigurationEntryOut] = []
    if is_admin:
        configs = (await db.execute(select(AILLMConfig))).scalars().all()
        ai_entries = [
            _entry(
                domain="ai_llm",
                resource_id=config.id,
                project_id=None,
                name=config.name,
                status="enabled" if config.enabled else "disabled",
                updated_at=config.updated_at,
                summary={
                    "provider": _safe_text(config.provider),
                    "model_name": _safe_text(config.model_name),
                    "enabled": bool(config.enabled),
                    "supports_vision": bool(config.supports_vision),
                    "has_api_key": bool(config.api_key_encrypted),
                },
                route="/system/ai-llm-configs",
                can_manage=True,
            )
            for config in configs
        ]
    sections.append(_section(*_SECTION_DEFINITIONS[3], ai_entries, available=is_admin))

    storage_entries: list[ConfigurationEntryOut] = []
    if is_admin:
        policies = (await db.execute(select(StoragePolicy))).scalars().all()
        storage_entries = [
            _entry(
                domain="storage_policy",
                resource_id=policy.id,
                project_id=None,
                name=policy.name,
                status="enabled" if policy.enabled else "disabled",
                updated_at=policy.updated_at,
                summary={
                    "prefix": _safe_text(policy.prefix),
                    "retention_days": policy.retention_days,
                    "max_size_gb": policy.max_size_gb,
                    "enabled": bool(policy.enabled),
                },
                route="/system/storage",
                can_manage=True,
            )
            for policy in policies
        ]
    sections.append(_section(*_SECTION_DEFINITIONS[4], storage_entries, available=is_admin))

    sections.append(
        _section(
            *_SECTION_DEFINITIONS[5],
            await _load_notification_entries(db, user, project_id, role_cache),
        )
    )

    performance_nodes = (await db.execute(select(PerformanceNode).order_by(PerformanceNode.name.asc()))).scalars().all()
    performance_entries = [
        _entry(
            domain="performance_node",
            resource_id=node.id,
            project_id=None,
            name=node.name,
            status=_safe_text(node.status, "offline"),
            updated_at=node.updated_at,
            summary={
                "node_id": _safe_text(node.node_id),
                "queue_name": _safe_text(node.queue_name),
                "enabled": bool(node.enabled),
                "max_vus": node.max_vus,
                "max_concurrency": node.max_concurrency,
                "executor_count": len(_safe_executors(node.capabilities)),
                "executors": _safe_executors(node.capabilities),
                "label_count": len(node.labels) if isinstance(node.labels, dict) else 0,
                "egress_allowlist_count": len(node.egress_allowlist) if isinstance(node.egress_allowlist, list) else 0,
            },
            route="/system/performance",
            can_manage=True,
        )
        for node in performance_nodes
    ]
    sections.append(_section(*_SECTION_DEFINITIONS[6], performance_entries))

    return ConfigurationCenterOverviewOut(checked_at=now, project_id=project_id, sections=sections)


def _revision_out(revision: ConfigurationRevision) -> ConfigurationRevisionOut:
    return ConfigurationRevisionOut(
        id=revision.id,
        domain=revision.domain,
        resource_id=revision.resource_id,
        project_id=revision.project_id,
        resource_name=revision.resource_name,
        fingerprint=revision.fingerprint,
        reason=revision.reason,
        redacted_payload=dict(revision.redacted_payload or {}),
        created_by=revision.created_by,
        created_at=revision.created_at,
        updated_at=revision.updated_at,
    )


def _revision_visibility_clause(user: User):
    if user.role == UserRole.admin:
        return None
    return or_(
        ConfigurationRevision.project_id.in_(visible_project_ids(user)),
        and_(
            ConfigurationRevision.project_id.is_(None),
            ConfigurationRevision.domain == "performance_node",
        ),
    )


def _assert_revision_domain_visible(user: User, domain: str | None) -> None:
    if user.role == UserRole.admin or domain not in {"ai_llm", "storage_policy"}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限查看此配置版本")


@router.post(
    "/revisions",
    response_model=ConfigurationRevisionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_configuration_revision(
    body: ConfigurationRevisionCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
) -> ConfigurationRevisionOut:
    """Persist one encrypted snapshot of an existing configuration resource."""

    try:
        snapshot = await load_configuration_snapshot(db, user, body.domain, body.resource_id)
    except ConfigurationSnapshotNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigurationSnapshotForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ConfigurationSnapshotUnsupported as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    revision = ConfigurationRevision(
        domain=snapshot.domain,
        resource_id=snapshot.resource_id,
        project_id=snapshot.project_id,
        resource_name=snapshot.resource_name,
        payload_encrypted=snapshot.payload_encrypted,
        redacted_payload=snapshot.redacted_payload,
        fingerprint=snapshot.fingerprint,
        reason=body.reason,
        created_by=user.id,
    )
    db.add(revision)
    await db.flush()
    await write_audit_log(
        db,
        action="configuration_revision_create",
        resource_type="configuration_revision",
        resource_id=revision.id,
        user_id=user.id,
        username=user.username,
        project_id=revision.project_id,
        detail=(
            f"创建配置版本: domain={revision.domain}, resource_id={revision.resource_id}, "
            f"fingerprint={revision.fingerprint}"
        ),
    )
    await db.commit()
    await db.refresh(revision)
    return _revision_out(revision)


@router.get("/revisions", response_model=list[ConfigurationRevisionOut])
async def list_configuration_revisions(
    domain: str | None = Query(default=None),
    resource_id: int | None = Query(default=None, ge=1),
    project_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
) -> list[ConfigurationRevisionOut]:
    """List safe revision history visible to the current engineer."""

    if resource_id is not None and not domain:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="按资源查询时必须指定配置域")
    if domain and domain not in SUPPORTED_SNAPSHOT_DOMAINS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的配置域")
    _assert_revision_domain_visible(user, domain)
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)

    statement = select(ConfigurationRevision).order_by(
        ConfigurationRevision.created_at.desc(), ConfigurationRevision.id.desc()
    )
    visibility = _revision_visibility_clause(user)
    if visibility is not None:
        statement = statement.where(visibility)
    if domain:
        statement = statement.where(ConfigurationRevision.domain == domain)
    if resource_id is not None:
        statement = statement.where(ConfigurationRevision.resource_id == resource_id)
    if project_id is not None:
        statement = statement.where(ConfigurationRevision.project_id == project_id)
    revisions = (await db.execute(statement.limit(limit))).scalars().all()
    return [_revision_out(revision) for revision in revisions]
