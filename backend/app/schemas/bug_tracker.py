from pydantic import BaseModel, Field
from datetime import datetime
from app.models.bug_tracker import TrackerType


class BugTrackerCreate(BaseModel):
    name: str
    project_id: int
    tracker_type: TrackerType
    config: dict = Field(default_factory=dict)
    field_mapping: dict = Field(default_factory=dict)
    is_enabled: bool = True


class BugTrackerUpdate(BaseModel):
    name: str | None = None
    tracker_type: TrackerType | None = None
    config: dict | None = None
    field_mapping: dict | None = None
    is_enabled: bool | None = None


class BugTrackerOut(BaseModel):
    id: int
    name: str
    project_id: int
    tracker_type: TrackerType
    config: dict
    field_mapping: dict
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BugTrackerConnectionTestRequest(BaseModel):
    tracker_id: int | None = None
    tracker_type: TrackerType
    config: dict = Field(default_factory=dict)


class BugTrackerConnectionTestOut(BaseModel):
    ok: bool
    message: str


class BugStatusOut(BaseModel):
    bug_id: str
    status: str
    bug_url: str | None = None


# ── 创建缺陷 ─────────────────────────────────────────────
class CreateBugRequest(BaseModel):
    tracker_id: int
    step_index: int | None = None  # 可选，指定某个步骤；为空则取 run 级错误


class BugResultOut(BaseModel):
    bug_id: str
    bug_url: str
    title: str
    duplicate_of: str | None = None
    attachment_uploaded: bool = False
