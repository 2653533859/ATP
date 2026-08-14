from datetime import datetime

from pydantic import BaseModel, Field


class RunRetentionPreviewOut(BaseModel):
    cutoff: datetime
    retention_days: int
    plan_runs: int
    suite_runs: int
    test_runs: int
    mobile_runs: int
    estimated_objects: int
    estimated_objects_sampled: bool


class RunRetentionExecuteIn(BaseModel):
    days: int | None = None


class ProjectRetentionCleanup(BaseModel):
    project_id: int
    project_name: str
    retention_days: int
    plan_runs: int
    suite_runs: int
    test_runs: int
    mobile_runs: int
    deleted_objects: int


class RunRetentionExecuteOut(BaseModel):
    cutoff: datetime
    retention_days: int
    plan_runs: int
    suite_runs: int
    test_runs: int
    mobile_runs: int
    deleted_objects: int
    projects: list[ProjectRetentionCleanup] = []


# P1.4 项目维度保留预览
class _ProjectRetentionPreview(BaseModel):
    project_id: int
    project_name: str
    retention_days: int
    plan_runs: int
    suite_runs: int
    test_runs: int = 0
    mobile_runs: int = 0
    estimated_objects: int = 0
    estimated_objects_sampled: bool = False
    note: str | None = None


class _GlobalRetentionPreview(BaseModel):
    retention_days: int
    plan_runs: int
    suite_runs: int
    test_runs: int
    mobile_runs: int
    estimated_objects: int
    estimated_objects_sampled: bool


class RunRetentionPerProjectOut(BaseModel):
    global_: _GlobalRetentionPreview = Field(alias="global")
    projects: list[_ProjectRetentionPreview]

    model_config = {"populate_by_name": True}
