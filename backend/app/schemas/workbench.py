"""Schemas for the workbench and unified task center."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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


class WorkbenchTaskRef(BaseModel):
    task_type: WorkbenchTaskType
    run_id: int = Field(ge=1)


class WorkbenchBatchActionIn(BaseModel):
    action: WorkbenchAction
    tasks: list[WorkbenchTaskRef] = Field(min_length=1, max_length=50)


class WorkbenchBatchActionOut(BaseModel):
    action: WorkbenchAction
    requested: int
    processed: int
    results: list[WorkbenchTaskActionOut] = Field(default_factory=list)
    failures: list[dict] = Field(default_factory=list)
