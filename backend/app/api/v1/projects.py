import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_project_access,
    get_current_user,
    require_admin,
    require_engineer,
    require_project_access,
    require_project_writable_access,
)
from app.api.v1.statistics import invalidate_stats_cache
from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.ai_llm_config import AILLMConfig
from app.models.dataset import TestDataset
from app.models.environment import Environment, EnvVariable
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject
from app.schemas.project import (
    ModuleCreate,
    ModuleOut,
    ModuleTree,
    ModuleUpdate,
    ProjectCreate,
    ProjectCopyIn,
    ProjectExportPayload,
    ProjectImportIn,
    ProjectImportOut,
    ProjectImportPreviewOut,
    ProjectOut,
    ProjectUpdate,
)
from app.schemas.user_project import (
    AuditLogOut,
    PaginatedAuditLogsOut,
    ProjectMemberAddIn,
    ProjectMemberOut,
    ProjectMemberUpdateIn,
)
from app.services.project_templates import get_project_template
from app.services.project_transfer import build_project_export, sanitize_json_value
from app.services.dataset_storage import DatasetStorageLimitError, validate_dataset_rows_size
from app.services.audit import write_audit_log

router = APIRouter(tags=["项目管理"])


def _normalize_code(name: str, fallback_prefix: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", " ", name or "").strip()
    if compact:
        parts = [part[:4].upper() for part in compact.split()[:3]]
        merged = "".join(parts)
        if merged:
            return merged[:12]
    return fallback_prefix


async def _audit_project_action(db: AsyncSession, action: str, project_id: int, actor, detail: str | None = None):
    await write_audit_log(
        db,
        action=action,
        resource_type="project",
        resource_id=project_id,
        project_id=project_id,
        user_id=getattr(actor, "id", None),
        username=getattr(actor, "username", ""),
        detail=detail,
    )


async def _load_project_export(db: AsyncSession, project: Project) -> ProjectExportPayload:
    module_result = await db.execute(select(Module).where(Module.project_id == project.id).order_by(Module.id))
    modules = list(module_result.scalars().all())
    environment_result = await db.execute(
        select(Environment).where(Environment.project_id == project.id).order_by(Environment.id)
    )
    environments = list(environment_result.scalars().all())
    environment_ids = [environment.id for environment in environments]
    variables: list[EnvVariable] = []
    if environment_ids:
        variable_result = await db.execute(select(EnvVariable).where(EnvVariable.env_id.in_(environment_ids)))
        variables = list(variable_result.scalars().all())
    dataset_result = await db.execute(
        select(TestDataset).where(TestDataset.project_id == project.id).order_by(TestDataset.id)
    )
    datasets = list(dataset_result.scalars().all())
    ai_model = await db.get(AILLMConfig, project.ai_llm_config_id) if project.ai_llm_config_id else None
    return build_project_export(project, modules, environments, variables, datasets, ai_model)


async def _project_code_exists(db: AsyncSession, project_code: str | None) -> bool:
    if not project_code:
        return False
    result = await db.execute(select(Project.id).where(Project.project_code == project_code))
    return result.scalar_one_or_none() is not None


async def _preview_project_import(db: AsyncSession, body: ProjectImportIn) -> ProjectImportPreviewOut:
    payload = body.payload
    conflicts: list[str] = []
    if await _project_code_exists(db, payload.project.project_code):
        conflicts.append(f"项目编码已存在：{payload.project.project_code}")
    warnings = list(payload.warnings)
    if payload.project.ai_model:
        warnings.append("导入时仅按模型名称匹配现有 AI 配置，匹配不到时不会绑定模型。")
    return ProjectImportPreviewOut(
        valid=not conflicts or body.conflict_policy == "rename",
        conflicts=conflicts,
        warnings=list(dict.fromkeys(warnings)),
        project_name=payload.project.name,
        project_code=payload.project.project_code,
        summary={
            "modules": len(payload.modules),
            "environments": len(payload.environments),
            "datasets": len(payload.datasets),
            "variables": sum(len(environment.variables) for environment in payload.environments),
        },
    )


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # admin 看全部；非 admin 仅看自己在 user_projects 里的项目
    if current_user.role == UserRole.admin:
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
        return [
            ProjectOut.model_validate(project).model_copy(update={"current_user_role": ProjectRole.owner})
            for project in result.scalars().all()
        ]
    result = await db.execute(
        select(Project, UserProject.role)
        .join(UserProject, UserProject.project_id == Project.id)
        .where(UserProject.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    return [
        ProjectOut.model_validate(project).model_copy(update={"current_user_role": role})
        for project, role in result.all()
    ]


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    payload = body.model_dump()
    payload.pop("template", None)
    payload["project_code"] = payload.get("project_code") or _normalize_code(body.name, "PROJECT")
    project = Project(**payload, owner_id=current_user.id)
    db.add(project)
    await db.flush()
    template = get_project_template(getattr(body, "template", "blank"))
    for sort_order, module_name in enumerate(template.modules):
        db.add(
            Module(
                name=module_name,
                module_code=_normalize_code(module_name, "MODULE"),
                project_id=project.id,
                sort_order=sort_order,
            )
        )
    if template.environment_name:
        db.add(Environment(name=template.environment_name, project_id=project.id))
    if template.dataset_name:
        rows = [dict(row) for row in template.dataset_rows]
        schema_fields = [{"name": key, "type": "string", "required": False, "default": None} for key in rows[0]]
        db.add(
            TestDataset(
                name=template.dataset_name,
                description="由项目模板生成的示例数据，可直接替换。",
                project_id=project.id,
                format="json",
                rows=rows,
                schema_fields=schema_fields,
                validation_policy="soft",
                creator_id=current_user.id,
            )
        )
    # P3.C 创建者自动获得项目 owner 角色
    db.add(UserProject(user_id=current_user.id, project_id=project.id, role=ProjectRole.owner))
    await db.commit()
    await invalidate_stats_cache()
    await db.refresh(project)
    return project


@router.post("/projects/import/preview", response_model=ProjectImportPreviewOut)
async def preview_project_import(
    body: ProjectImportIn,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    return await _preview_project_import(db, body)


@router.post("/projects/import", response_model=ProjectImportOut, status_code=status.HTTP_201_CREATED)
async def import_project(
    body: ProjectImportIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    preview = await _preview_project_import(db, body)
    if not preview.valid:
        raise HTTPException(status_code=409, detail={"message": "项目编码冲突", "conflicts": preview.conflicts})

    payload = body.payload
    sanitized_dataset_rows = []
    for dataset_payload in payload.datasets:
        rows = [sanitize_json_value(row) for row in dataset_payload.rows]
        try:
            validate_dataset_rows_size(rows)
        except DatasetStorageLimitError as exc:
            raise HTTPException(status_code=400, detail=f"数据集「{dataset_payload.name}」{exc}") from exc
        sanitized_dataset_rows.append(rows)

    project_code = payload.project.project_code or _normalize_code(payload.project.name, "PROJECT")
    if await _project_code_exists(db, project_code):
        project_code = f"{_normalize_code(payload.project.name, 'PROJECT')[:24]}-{uuid4().hex[:6].upper()}"

    ai_llm_config_id = None
    warnings = list(preview.warnings)
    if payload.project.ai_model:
        ai_result = await db.execute(
            select(AILLMConfig).where(
                AILLMConfig.name == payload.project.ai_model.name,
                AILLMConfig.provider == payload.project.ai_model.provider,
                AILLMConfig.model_name == payload.project.ai_model.model_name,
            )
        )
        ai_config = ai_result.scalar_one_or_none()
        if ai_config:
            ai_llm_config_id = ai_config.id
        else:
            warnings.append("未找到匹配的 AI 模型配置，项目暂未绑定 AI。")

    project = Project(
        name=payload.project.name,
        project_code=project_code,
        description=payload.project.description,
        owner_id=current_user.id,
        ai_llm_config_id=ai_llm_config_id,
        status="active",
        run_retention_days_override=payload.project.run_retention_days_override,
    )
    db.add(project)
    await db.flush()

    pending_modules = list(payload.modules)
    imported_module_ids: dict[int, int] = {}
    while pending_modules:
        ready = [item for item in pending_modules if item.parent_id is None or item.parent_id in imported_module_ids]
        if not ready:
            ready = pending_modules[:1]
        for source_module in ready:
            module = Module(
                name=source_module.name,
                module_code=source_module.module_code,
                project_id=project.id,
                parent_id=imported_module_ids.get(source_module.parent_id),
                sort_order=source_module.sort_order,
            )
            db.add(module)
            await db.flush()
            imported_module_ids[source_module.id] = module.id
            pending_modules.remove(source_module)

    imported_variables = 0
    for environment_payload in payload.environments:
        environment = Environment(
            name=environment_payload.name,
            description=environment_payload.description,
            project_id=project.id,
        )
        db.add(environment)
        await db.flush()
        for variable_payload in environment_payload.variables:
            if variable_payload.redacted or variable_payload.value is None:
                continue
            db.add(
                EnvVariable(
                    env_id=environment.id,
                    key=variable_payload.key,
                    value=variable_payload.value,
                    is_secret=variable_payload.is_secret,
                )
            )
            imported_variables += 1

    for dataset_payload, rows in zip(payload.datasets, sanitized_dataset_rows, strict=True):
        db.add(
            TestDataset(
                name=dataset_payload.name,
                description=dataset_payload.description,
                project_id=project.id,
                format=dataset_payload.format,
                rows=rows,
                schema_fields=[sanitize_json_value(field) for field in dataset_payload.schema_fields],
                validation_policy=dataset_payload.validation_policy,
                creator_id=current_user.id,
            )
        )

    db.add(UserProject(user_id=current_user.id, project_id=project.id, role=ProjectRole.owner))
    await _audit_project_action(
        db,
        "project_imported",
        project.id,
        current_user,
        detail=f"modules={len(imported_module_ids)}, environments={len(payload.environments)}, datasets={len(payload.datasets)}",
    )
    await db.commit()
    await invalidate_stats_cache()
    await db.refresh(project)
    return ProjectImportOut(
        project=project,
        imported={
            "modules": len(imported_module_ids),
            "environments": len(payload.environments),
            "variables": imported_variables,
            "datasets": len(payload.datasets),
        },
        warnings=list(dict.fromkeys(warnings)),
    )


@router.get("/projects/{project_id}/export", response_model=ProjectExportPayload)
async def export_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_project_access(ProjectRole.viewer)),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _load_project_export(db, project)


@router.post("/projects/{project_id}/copy", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def copy_project(
    project_id: int,
    body: ProjectCopyIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_project_writable_access(ProjectRole.owner)),
):
    source = await db.get(Project, project_id)
    if not source:
        raise HTTPException(status_code=404, detail="Project not found")

    # 项目编码必须独立于源项目；短 UUID 避免同名复制撞上唯一索引。
    project_code = f"{_normalize_code(body.name, 'PROJECT')[:24]}-{uuid4().hex[:6].upper()}"
    copied = Project(
        name=body.name,
        project_code=project_code,
        description=source.description,
        owner_id=current_user.id,
        ai_llm_config_id=source.ai_llm_config_id,
        status="active",
        run_retention_days_override=source.run_retention_days_override,
    )
    db.add(copied)
    await db.flush()

    result = await db.execute(select(Module).where(Module.project_id == project_id).order_by(Module.id))
    pending = list(result.scalars().all())
    copied_ids: dict[int, int] = {}
    while pending:
        ready = [item for item in pending if item.parent_id is None or item.parent_id in copied_ids]
        if not ready:
            # 防止历史脏数据中的循环 parent_id 阻塞整个复制事务。
            ready = pending[:1]
        for source_module in ready:
            module = Module(
                name=source_module.name,
                module_code=source_module.module_code,
                project_id=copied.id,
                parent_id=copied_ids.get(source_module.parent_id),
                sort_order=source_module.sort_order,
            )
            db.add(module)
            await db.flush()
            copied_ids[source_module.id] = module.id
            pending.remove(source_module)

    db.add(UserProject(user_id=current_user.id, project_id=copied.id, role=ProjectRole.owner))
    await _audit_project_action(db, "project_copied", copied.id, current_user, detail=f"source_project_id={project_id}")
    await db.commit()
    await invalidate_stats_cache()
    await db.refresh(copied)
    return copied


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_project_access(ProjectRole.viewer)),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_project_writable_access(ProjectRole.owner)),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    payload = body.model_dump(exclude_none=True)
    if payload.get("name") and not payload.get("project_code") and not project.project_code:
        payload["project_code"] = _normalize_code(payload["name"], "PROJECT")

    for key, value in payload.items():
        setattr(project, key, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_project_access(ProjectRole.owner)),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    await db.delete(project)
    await db.commit()
    await invalidate_stats_cache()


@router.post("/projects/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access(ProjectRole.owner)),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.status = "archived"
    await _audit_project_action(db, "project_archived", project_id, current_user)
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/projects/{project_id}/restore", response_model=ProjectOut)
async def restore_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_access(ProjectRole.owner)),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.status = "active"
    await _audit_project_action(db, "project_restored", project_id, current_user)
    await db.commit()
    await db.refresh(project)
    return project


def _build_tree(modules: list[Module]) -> list[ModuleTree]:
    id_map = {
        module.id: ModuleTree(
            id=module.id,
            name=module.name,
            module_code=getattr(module, "module_code", None),
            project_id=module.project_id,
            parent_id=module.parent_id,
            sort_order=module.sort_order,
            created_at=module.created_at,
            children=[],
        )
        for module in modules
    }
    roots: list[ModuleTree] = []
    for node in id_map.values():
        if node.parent_id and node.parent_id in id_map:
            id_map[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return sorted(roots, key=lambda item: item.sort_order)


@router.get("/projects/{project_id}/modules", response_model=list[ModuleTree])
async def list_modules(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_project_access(ProjectRole.viewer)),
):
    result = await db.execute(select(Module).where(Module.project_id == project_id).order_by(Module.sort_order))
    return _build_tree(result.scalars().all())


@router.post("/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
async def create_module(
    body: ModuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = body.model_dump()
    await assert_project_access(db, current_user, payload["project_id"], ProjectRole.editor)
    payload["module_code"] = payload.get("module_code") or _normalize_code(body.name, "MODULE")
    module = Module(**payload)
    db.add(module)
    await db.commit()
    await invalidate_stats_cache()
    await db.refresh(module)
    return module


@router.patch("/modules/{module_id}", response_model=ModuleOut)
async def update_module(
    module_id: int,
    body: ModuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")
    await assert_project_access(db, current_user, module.project_id, ProjectRole.editor)

    payload = body.model_dump(exclude_none=True)
    if payload.get("name") and not payload.get("module_code") and not module.module_code:
        payload["module_code"] = _normalize_code(payload["name"], "MODULE")

    for key, value in payload.items():
        setattr(module, key, value)
    await db.commit()
    await db.refresh(module)
    return module


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    module_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")
    await assert_project_access(db, current_user, module.project_id, ProjectRole.editor)
    await db.delete(module)
    await db.commit()
    await invalidate_stats_cache()


# ─── P3.C 项目成员管理 ─────────────────────────────────────────────────────


@router.get("/projects/{project_id}/members", response_model=list[ProjectMemberOut])
async def list_project_members(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_project_access(ProjectRole.viewer)),
):
    stmt = (
        select(UserProject, User)
        .join(User, User.id == UserProject.user_id)
        .where(UserProject.project_id == project_id)
        .order_by(UserProject.created_at.asc())
    )
    result = await db.execute(stmt)
    items: list[ProjectMemberOut] = []
    for up, user in result.all():
        items.append(
            ProjectMemberOut(
                id=up.id,
                user_id=user.id,
                username=user.username,
                email=user.email,
                role=up.role.value if hasattr(up.role, "value") else str(up.role),
                created_at=up.created_at,
            )
        )
    return items


@router.post(
    "/projects/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member(
    project_id: int,
    body: ProjectMemberAddIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_writable_access(ProjectRole.owner)),
):
    user = await db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    existing = await db.execute(
        select(UserProject).where(
            UserProject.user_id == body.user_id,
            UserProject.project_id == project_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户已在项目成员列表中")

    up = UserProject(
        user_id=body.user_id,
        project_id=project_id,
        role=ProjectRole(body.role),
    )
    db.add(up)
    await _audit_project_action(db, "project_member_added", project_id, current_user, detail=f"user_id={body.user_id}")
    await db.commit()
    await db.refresh(up)
    return ProjectMemberOut(
        id=up.id,
        user_id=user.id,
        username=user.username,
        email=user.email,
        role=up.role.value,
        created_at=up.created_at,
    )


@router.patch(
    "/projects/{project_id}/members/{user_id}",
    response_model=ProjectMemberOut,
)
async def update_project_member(
    project_id: int,
    user_id: int,
    body: ProjectMemberUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_writable_access(ProjectRole.owner)),
):
    stmt = select(UserProject).where(UserProject.user_id == user_id, UserProject.project_id == project_id)
    result = await db.execute(stmt)
    up = result.scalar_one_or_none()
    if not up:
        raise HTTPException(status_code=404, detail="成员不存在")

    up.role = ProjectRole(body.role)
    await _audit_project_action(
        db,
        "project_member_role_updated",
        project_id,
        current_user,
        detail=f"user_id={user_id}, role={body.role}",
    )
    await db.commit()
    await db.refresh(up)
    user = await db.get(User, user_id)
    return ProjectMemberOut(
        id=up.id,
        user_id=up.user_id,
        username=user.username if user else "",
        email=user.email if user else "",
        role=up.role.value,
        created_at=up.created_at,
    )


@router.delete(
    "/projects/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_member(
    project_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_writable_access(ProjectRole.owner)),
):
    stmt = select(UserProject).where(UserProject.user_id == user_id, UserProject.project_id == project_id)
    result = await db.execute(stmt)
    up = result.scalar_one_or_none()
    if not up:
        raise HTTPException(status_code=404, detail="成员不存在")
    # 防止移除最后一个 owner
    if up.role == ProjectRole.owner:
        owner_count_stmt = select(func.count(UserProject.id)).where(
            UserProject.project_id == project_id,
            UserProject.role == ProjectRole.owner,
        )
        owner_count = (await db.execute(owner_count_stmt)).scalar_one()
        if owner_count <= 1:
            raise HTTPException(status_code=400, detail="不能移除最后一个 owner")
    await db.delete(up)
    await _audit_project_action(db, "project_member_removed", project_id, current_user, detail=f"user_id={user_id}")
    await db.commit()


# ─── P3.C 审计日志查询 ─────────────────────────────────────────────────────


@router.get("/audit-logs", response_model=PaginatedAuditLogsOut)
async def list_audit_logs(
    project_id: int | None = Query(None),
    action: str | None = Query(None),
    user_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    where_clauses = []
    if project_id is not None:
        where_clauses.append(AuditLog.project_id == project_id)
    if action:
        where_clauses.append(AuditLog.action == action)
    if user_id is not None:
        where_clauses.append(AuditLog.user_id == user_id)

    count_stmt = select(func.count(AuditLog.id))
    if where_clauses:
        count_stmt = count_stmt.where(*where_clauses)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if where_clauses:
        stmt = stmt.where(*where_clauses)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(stmt)).scalars().all()

    return PaginatedAuditLogsOut(items=items, total=total, page=page, page_size=page_size)
