from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.models.project import Project, Module
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut,
    ModuleCreate, ModuleUpdate, ModuleOut, ModuleTree,
)
from app.api.deps import get_current_user

router = APIRouter(tags=["项目管理"])


# ── Projects ─────────────────────────────────────────────
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
    project = Project(**body.model_dump(), owner_id=current_user.id)
    db.add(project)
    await db.commit()
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
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(project, k, v)
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


# ── Modules ──────────────────────────────────────────────
def _build_tree(modules: list[Module]) -> list[ModuleTree]:
    id_map = {
        m.id: ModuleTree(
            id=m.id,
            name=m.name,
            project_id=m.project_id,
            parent_id=m.parent_id,
            sort_order=m.sort_order,
            created_at=m.created_at,
            children=[],
        )
        for m in modules
    }
    roots = []
    for node in id_map.values():
        if node.parent_id and node.parent_id in id_map:
            id_map[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return sorted(roots, key=lambda x: x.sort_order)


@router.get("/projects/{project_id}/modules", response_model=list[ModuleTree])
async def list_modules(project_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(Module).where(Module.project_id == project_id).order_by(Module.sort_order)
    )
    modules = result.scalars().all()
    return _build_tree(modules)


@router.post("/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
async def create_module(body: ModuleCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    module = Module(**body.model_dump())
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module


@router.patch("/modules/{module_id}", response_model=ModuleOut)
async def update_module(
    module_id: int, body: ModuleUpdate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)
):
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(module, k, v)
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
