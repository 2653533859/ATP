"""Pydantic schemas for global variables."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.global_variable import ScopeType


class GlobalVariableCreate(BaseModel):
    scope_type: ScopeType = ScopeType.global_scope
    project_id: Optional[int] = None
    key: str = Field(..., min_length=1, max_length=256)
    value_encrypted: str = Field(..., min_length=1)
    is_secret: bool = False
    description: Optional[str] = None
    created_by: Optional[int] = None


class GlobalVariableUpdate(BaseModel):
    scope_type: Optional[ScopeType] = None
    project_id: Optional[int] = None
    key: Optional[str] = Field(None, min_length=1, max_length=256)
    value_encrypted: Optional[str] = Field(None, min_length=1)
    is_secret: Optional[bool] = None
    description: Optional[str] = None
    updated_by: Optional[int] = None


class GlobalVariableOut(BaseModel):
    id: int
    scope_type: ScopeType
    project_id: Optional[int] = None
    key: str
    value_encrypted: str
    is_secret: bool
    description: Optional[str] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GlobalVariableRead(BaseModel):
    """Schema for reading a variable value. Secrets are masked."""

    id: int
    scope_type: ScopeType
    project_id: Optional[int] = None
    key: str
    value: str  # actual value for non-secrets, masked for secrets
    is_secret: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
