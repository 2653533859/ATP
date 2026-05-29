from typing import Any

from pydantic import BaseModel, Field


class StructuredHealingPatchIn(BaseModel):
    case_type: str
    step_index: int = Field(ge=0)
    action: str
    params: dict[str, Any] = Field(default_factory=dict)


class StructuredHealingSuggestionIn(BaseModel):
    root_cause: str
    confidence: float = Field(ge=0, le=1)
    patch: StructuredHealingPatchIn | None = None
    regression_scope: str = "single_case"
    notes: list[str] = Field(default_factory=list)


class HealingPatchPreviewRequest(BaseModel):
    case_id: int = Field(ge=1)
    raw_suggestion: str | None = Field(
        default=None,
        description="Raw LLM output. When present, backend parses the structured JSON contract.",
    )
    suggestion: StructuredHealingSuggestionIn | None = None


class HealingPatchApplyRequest(HealingPatchPreviewRequest):
    trigger_regression: bool = False
    env_id: int | None = None
    extra_vars: dict[str, Any] = Field(default_factory=dict)
    source_run_id: int | None = Field(default=None, ge=1)
    source_step_id: int | None = Field(default=None, ge=1)


class HealingPatchPreviewOut(BaseModel):
    accepted: bool
    reasons: list[str] = Field(default_factory=list)
    normalized_patch: dict[str, Any] | None = None
    preview_config: dict[str, Any] | None = None


class HealingPatchApplyOut(BaseModel):
    accepted: bool
    reasons: list[str] = Field(default_factory=list)
    case_id: int
    snapshot_version: int | None = None
    normalized_patch: dict[str, Any] | None = None
    regression_run_id: int | None = None
    preview_config: dict[str, Any] | None = None
