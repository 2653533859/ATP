import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.statistics import invalidate_stats_cache
from app.core.database import get_db
from app.models.project import Module, Project
from app.models.user import User
from app.schemas.project import (
    ModuleCreate,
    ModuleOut,
    ModuleTree,
    ModuleUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
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
async def list_projects(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
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
    await db.commit()
    await invalidate_stats_cache()
    await db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
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
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
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
async def list_modules(project_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(Module).where(Module.project_id == project_id).order_by(Module.sort_order)
    )
    return _build_tree(result.scalars().all())


@router.post("/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
async def create_module(body: ModuleCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    payload = body.model_dump()
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
    _=Depends(get_current_user),
):
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")

    payload = body.model_dump(exclude_none=True)
    if payload.get("name") and not payload.get("module_code") and not module.module_code:
        payload["module_code"] = _normalize_code(payload["name"], "MODULE")

    for key, value in payload.items():
        setattr(module, key, value)
    await db.commit()
    await db.refresh(module)
    return module


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(module_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")
    await db.delete(module)
    await db.commit()
    await invalidate_stats_cache()
