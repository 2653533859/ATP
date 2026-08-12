from typing import Any, Literal

from pydantic import BaseModel, Field
from datetime import datetime

from app.models.user_project import ProjectRole


# ── Project ─────────────────────────────────────────────
ProjectTemplate = Literal["blank", "api", "web", "android", "full"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    project_code: str | None = None
    description: str | None = None
    ai_llm_config_id: int | None = None
    run_retention_days_override: int | None = None
    template: ProjectTemplate = "blank"


class ProjectCopyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


TransferConflictPolicy = Literal["fail", "rename"]


class ProjectTransferAIModel(BaseModel):
    name: str
    provider: str
    model_name: str
    supports_vision: bool = False


class ProjectTransferModule(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=128)
    module_code: str | None = None
    parent_id: int | None = None
    sort_order: int = 0


class ProjectTransferVariable(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    value: str | None = None
    is_secret: bool = False
    redacted: bool = False


class ProjectTransferEnvironment(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    variables: list[ProjectTransferVariable] = Field(default_factory=list, max_length=200)


class ProjectTransferDataset(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    format: Literal["csv", "json"] = "json"
    rows: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    schema_fields: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    validation_policy: Literal["soft", "hard"] = "soft"


class ProjectTransferProject(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    project_code: str | None = Field(default=None, max_length=32)
    description: str | None = None
    run_retention_days_override: int | None = None
    ai_model: ProjectTransferAIModel | None = None


class ProjectExportPayload(BaseModel):
    format_version: Literal["1"] = "1"
    exported_at: datetime
    project: ProjectTransferProject
    modules: list[ProjectTransferModule] = Field(default_factory=list, max_length=1000)
    environments: list[ProjectTransferEnvironment] = Field(default_factory=list, max_length=200)
    datasets: list[ProjectTransferDataset] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=50)


class ProjectImportIn(BaseModel):
    payload: ProjectExportPayload
    conflict_policy: TransferConflictPolicy = "fail"


class ProjectImportPreviewOut(BaseModel):
    valid: bool
    conflicts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    project_name: str
    project_code: str | None = None
    summary: dict[str, int] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = None
    project_code: str | None = None
    description: str | None = None
    ai_llm_config_id: int | None = None
    run_retention_days_override: int | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    project_code: str | None
    description: str | None
    owner_id: int
    ai_llm_config_id: int | None = None
    status: str
    run_retention_days_override: int | None = None
    current_user_role: ProjectRole | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectImportOut(BaseModel):
    project: ProjectOut
    imported: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# ── Module ───────────────────────────────────────────────
class ModuleCreate(BaseModel):
    name: str
    module_code: str | None = None
    project_id: int
    parent_id: int | None = None
    sort_order: int = 0


class ModuleUpdate(BaseModel):
    name: str | None = None
    module_code: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None


class ModuleOut(BaseModel):
    id: int
    name: str
    module_code: str | None
    project_id: int
    parent_id: int | None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ModuleTree(ModuleOut):
    children: list["ModuleTree"] = []
