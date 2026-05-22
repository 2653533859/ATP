import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_project_access,
    get_current_user,
    require_admin,
    require_project_access,
)
from app.api.v1.statistics import invalidate_stats_cache
from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject
from app.schemas.project import (
    ModuleCreate,
    ModuleOut,
    ModuleTree,
    ModuleUpdate,
    ProjectCreate,
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

router = APIRouter(tags=["项目管理"])


def _normalize_code(name: str, fallback_prefix: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", " ", name or "").strip()
    if compact:
        parts = [part[:4].upper() for part in compact.split()[:3]]
        merged = "".join(parts)
        if merged:
            return merged[:12]
    return fallback_prefix


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # admin 看全部；非 admin 仅看自己在 user_projects 里的项目
    stmt = select(Project).order_by(Project.created_at.desc())
    if current_user.role != UserRole.admin:
        stmt = stmt.join(UserProject, UserProject.project_id == Project.id).where(
            UserProject.user_id == current_user.id
        )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = body.model_dump()
    payload["project_code"] = payload.get("project_code") or _normalize_code(body.name, "PROJECT")
    project = Project(**payload, owner_id=current_user.id)
    db.add(project)
    await db.flush()
    # P3.C 创建者自动获得项目 owner 角色
    db.add(UserProject(user_id=current_user.id, project_id=project.id, role=ProjectRole.owner))
    await db.commit()
    await invalidate_stats_cache()
    await db.refresh(project)
    return project


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
    _=Depends(require_project_access(ProjectRole.owner)),
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
    result = await db.execute(
        select(Module).where(Module.project_id == project_id).order_by(Module.sort_order)
    )
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
    _=Depends(require_project_access(ProjectRole.owner)),
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
    _=Depends(require_project_access(ProjectRole.owner)),
):
    stmt = select(UserProject).where(
        UserProject.user_id == user_id, UserProject.project_id == project_id
    )
    result = await db.execute(stmt)
    up = result.scalar_one_or_none()
    if not up:
        raise HTTPException(status_code=404, detail="成员不存在")

    up.role = ProjectRole(body.role)
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
    _=Depends(require_project_access(ProjectRole.owner)),
):
    stmt = select(UserProject).where(
        UserProject.user_id == user_id, UserProject.project_id == project_id
    )
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
