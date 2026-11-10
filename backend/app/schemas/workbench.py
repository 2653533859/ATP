"""Schemas for the workbench and unified task center."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class WorkbenchTodoItem(BaseModel):
    id: str
    kind: str
    priority: Literal["high", "medium", "low"]
    project_id: int | None = None
    project_name: str | None = None
    title: str
    description: str | None = None
    status: str
    created_at: datetime | None = None
    due_at: datetime | None = None
    path: str
    metadata: dict = Field(default_factory=dict)
    is_snoozed: bool = False
    snooze_reason: str | None = None
    snoozed_until: datetime | None = None


class WorkbenchTaskItem(BaseModel):
    id: str
    task_type: Literal["case", "suite", "plan", "android", "performance"]
    run_id: int
    source_id: int
    project_id: int | None = None
    project_name: str | None = None
    name: str
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    detail_path: str
    can_retry: bool = False
    can_stop: bool = False
    metadata: dict = Field(default_factory=dict)
    is_archived: bool = False
    archived_at: datetime | None = None


class WorkbenchOverviewOut(BaseModel):
    generated_at: datetime
    project_id: int | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    todos: list[WorkbenchTodoItem] = Field(default_factory=list)
    tasks: list[WorkbenchTaskItem] = Field(default_factory=list)
    has_more_todos: bool = False
    has_more_tasks: bool = False


class WorkbenchTaskPageOut(BaseModel):
    generated_at: datetime
    project_id: int | None = None
    status_filter: str | None = None
    task_type: str | None = None
    items: list[WorkbenchTaskItem] = Field(default_factory=list)
    total: int
    has_more: bool = False


WorkbenchTaskType = Literal["case", "suite", "plan", "android", "performance"]
WorkbenchAction = Literal["retry", "stop"]


class WorkbenchTaskActionOut(BaseModel):
    action: WorkbenchAction
    task_type: WorkbenchTaskType
    run_id: int
    new_run_id: int | None = None
    status: str
    message: str
    command_id: str = ""
    replayed: bool = False


class WorkbenchTaskRef(BaseModel):
    task_type: WorkbenchTaskType
    run_id: int = Field(ge=1)
    command_id: str | None = Field(default=None, min_length=1, max_length=128)


class WorkbenchBatchActionIn(BaseModel):
    action: WorkbenchAction
    tasks: list[WorkbenchTaskRef] = Field(min_length=1, max_length=50)


class WorkbenchBatchActionOut(BaseModel):
    action: WorkbenchAction
    requested: int
    processed: int
    results: list[WorkbenchTaskActionOut] = Field(default_factory=list)
    failures: list[dict] = Field(default_factory=list)


class WorkbenchTodoSnoozeIn(BaseModel):
    duration_hours: int = Field(default=24, ge=-1, le=720)  # -1 for indefinite
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("duration_hours")
    @classmethod
    def validate_duration_hours(cls, v: int) -> int:
        if v == 0:
            raise ValueError("duration_hours must be -1 (indefinite) or positive integer")
        return v


class WorkbenchTodoSnoozeOut(BaseModel):
    todo_id: str
    user_id: int
    reason: str | None = None
    snoozed_until: datetime | None = None
    created_at: datetime


class WorkbenchTaskArchiveIn(BaseModel):
    tasks: list[WorkbenchTaskRef] = Field(min_length=1, max_length=100)


class WorkbenchTaskArchiveOut(BaseModel):
    processed: int
    archived: bool
