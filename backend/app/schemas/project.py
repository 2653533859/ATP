from pydantic import BaseModel
from datetime import datetime


# ── Project ─────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Module ───────────────────────────────────────────────
class ModuleCreate(BaseModel):
    name: str
    project_id: int
    parent_id: int | None = None
    sort_order: int = 0


class ModuleUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None


class ModuleOut(BaseModel):
    id: int
    name: str
    project_id: int
    parent_id: int | None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ModuleTree(ModuleOut):
    children: list["ModuleTree"] = []
