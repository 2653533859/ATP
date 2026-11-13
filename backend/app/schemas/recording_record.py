"""录制历史与未保存草稿请求/响应模式定义。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RecordingKind = Literal["web", "android"]
RecordingSource = Literal["workbench", "case_drawer", "resume", "assets", "mirror", "visual_editor"]
RecordingStatus = Literal["draft", "saved", "stopped", "error"]


class RecordingArtifactOut(BaseModel):
    kind: str
    filename: str
    content_type: str
    size: int = 0
    object_name: str | None = None
    url: str | None = None


class RecordingRecordCreate(BaseModel):
    project_id: int = Field(..., gt=0)
    kind: RecordingKind
    source: RecordingSource = "workbench"
    session_id: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    target_url: str | None = Field(default=None, max_length=1024)
    browser: str | None = Field(default=None, max_length=32)
    device_id: int | None = Field(default=None, gt=0)
    device_serial: str | None = Field(default=None, max_length=128)
    case_id: int | None = Field(default=None, gt=0)
    status: RecordingStatus = "draft"
    steps: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    asset_ids: list[int] = Field(default_factory=list, max_length=500)
    summary: dict[str, Any] = Field(default_factory=dict)


class RecordingRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: RecordingStatus | None = None
    case_id: int | None = Field(default=None, gt=0)
    device_id: int | None = Field(default=None, gt=0)
    device_serial: str | None = Field(default=None, max_length=128)
    steps: list[dict[str, Any]] | None = Field(default=None, max_length=500)
    summary: dict[str, Any] | None = None


class RecordingRecordOut(BaseModel):
    id: int
    project_id: int
    owner_id: int | None
    kind: RecordingKind | str
    source: RecordingSource | str
    session_id: str | None = None
    title: str
    target_url: str | None = None
    browser: str | None = None
    device_id: int | None = None
    device_serial: str | None = None
    case_id: int | None = None
    status: RecordingStatus | str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    steps_count: int = 0
    assertion_count: int = 0
    asset_ids: list[int] = Field(default_factory=list)
    artifacts: dict[str, RecordingArtifactOut] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
