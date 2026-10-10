"""Public recovery metadata, excluding worker credentials and ownership tokens."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.execution_dispatch import ExecutionDispatchOut


class GroupChildState(BaseModel):
    kind: str
    run_id: int
    verified: bool
    status: str | None
    execution_uncertain: bool = False


class GroupExecutionState(BaseModel):
    kind: Literal["suite", "plan"]
    run_id: int
    revision: str
    run_status: str
    reason: str
    requires_reconciliation: bool
    cancel_requested_at: datetime | None
    can_cancel: bool
    dispatch: ExecutionDispatchOut | None = None
    lease_status: str | None = None
    lease_expires_at: datetime | None = None
    children: list[GroupChildState] = Field(default_factory=list)
    child_count: int = 0
    children_truncated: bool = False
    legacy_children_unverified: bool = False
    next_cursor: int | None = None
    has_more: bool = False
    active_children_count: int = 0
    terminal_children_count: int = 0


class GroupCancelResult(BaseModel):
    requested: bool
    pending: bool


class GroupCancelIn(BaseModel):
    expected_revision: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]+$")
