"""P3.C 项目成员管理 schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ProjectRoleLiteral = Literal["owner", "editor", "viewer"]


class ProjectMemberOut(BaseModel):
    id: int
    user_id: int
    username: str
    email: str
    role: ProjectRoleLiteral
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectMemberAddIn(BaseModel):
    user_id: int = Field(..., ge=1)
    role: ProjectRoleLiteral = "viewer"


class ProjectMemberUpdateIn(BaseModel):
    role: ProjectRoleLiteral


class AuditLogOut(BaseModel):
    id: int
    action: str
    resource_type: str
    resource_id: int | None = None
    user_id: int | None = None
    username: str
    detail: str | None = None
    ip_address: str
    project_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAuditLogsOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
