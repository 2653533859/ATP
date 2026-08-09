from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.case import TestCaseCreate


class CaseImportRequest(BaseModel):
    cases: list[TestCaseCreate] = Field(..., min_length=1, max_length=200)
    conflict_policy: Literal["fail", "skip", "replace"] = "fail"


class CaseImportConflict(BaseModel):
    index: int
    module_id: int
    name: str
    reason: str


class CaseImportPreviewOut(BaseModel):
    total: int
    valid_count: int
    invalid_count: int
    conflicts: list[CaseImportConflict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CaseImportOut(BaseModel):
    imported: int
    skipped_count: int
    case_ids: list[int] = Field(default_factory=list)
    conflicts: list[CaseImportConflict] = Field(default_factory=list)
