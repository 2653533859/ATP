from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.case import CaseStatus, CaseType, RunStatus


CasePriority = Literal["P0", "P1", "P2", "P3"]
CaseLevel = Literal["smoke", "core", "regression", "extended"]
ReviewStatus = Literal["pending", "approved", "rejected"]
AutomationStatus = Literal["manual", "semi_auto", "auto"]
ScriptStatus = Literal["generated", "missing", "not_applicable"]


class CaseFlakyStats(BaseModel):
    is_flaky: bool = False
    total_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    error_runs: int = 0
    failure_rate: float = 0.0
    window_size: int = 10


class CaseStepBase(BaseModel):
    action: str
    test_data: str | None = None
    expected_result: str | None = None
    is_key_step: bool = False
    remarks: str | None = None


class CaseStepCreate(CaseStepBase):
    step_no: int | None = Field(default=None, ge=1)


class CaseStepOut(CaseStepBase):
    id: int
    step_no: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestCaseCreate(BaseModel):
    name: str
    description: str | None = None
    summary: str | None = None
    case_type: CaseType
    module_id: int
    tags: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    priority: CasePriority = "P2"
    case_level: CaseLevel = "regression"
    owner_id: int | None = None
    automation_status: AutomationStatus = "auto"
    steps: list[CaseStepCreate] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    dataset_version: int | None = Field(default=None, ge=1)
    dataset_id: int | None = None  # P3.B 绑定数据集后参数化执行


class TestCaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    preconditions: list[str] | None = None
    postconditions: list[str] | None = None
    priority: CasePriority | None = None
    case_level: CaseLevel | None = None
    owner_id: int | None = None
    automation_status: AutomationStatus | None = None
    steps: list[CaseStepCreate] | None = None
    config: dict | None = None
    dataset_version: int | None = Field(default=None, ge=1)
    dataset_id: int | None = None  # 传 None 显式清除绑定


class TestCaseOut(BaseModel):
    id: int
    name: str
    description: str | None
    case_code: str
    summary: str
    case_type: CaseType
    status: CaseStatus
    priority: CasePriority
    case_level: CaseLevel
    review_status: ReviewStatus
    automation_status: AutomationStatus
    tags: list[str]
    module_id: int
    creator_id: int
    owner_id: int | None
    is_ready_for_execution: bool
    ai_generated: bool = False
    script_status: ScriptStatus = "not_applicable"
    dataset_id: int | None = None
    dataset_version: int | None = None
    flaky_stats: CaseFlakyStats = Field(default_factory=CaseFlakyStats)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestCaseDetailOut(TestCaseOut):
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by: int | None = None
    review_comment: str | None = None
    steps: list[CaseStepOut] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)


class CaseSnapshotOut(BaseModel):
    id: int
    case_id: int
    version: int
    name: str
    description: str | None
    tags: list[str]
    config: dict
    snapshot_data: dict = Field(default_factory=dict)
    updated_by: int
    updated_by_name: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedSnapshotsOut(BaseModel):
    items: list[CaseSnapshotOut]
    total: int
    page: int
    page_size: int


class CaseSnapshotManualCreate(BaseModel):
    """手动创建快照（不依赖编辑触发）。"""

    remark: str | None = Field(default=None, description="可选备注，覆盖 snapshot_data.remark")


class CaseSnapshotImport(BaseModel):
    """从 JSON 导入快照内容（创建一个新版本，作为最高版本号）。"""

    snapshot_data: dict
    name: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)


class CaseCloneFromSnapshotRequest(BaseModel):
    """从历史快照克隆为新用例（不影响原用例）。"""

    module_id: int | None = Field(default=None, description="目标模块，默认沿用原用例")
    name: str | None = Field(default=None, description="新用例名称，默认在原名后加副本标记")


class CaseSnapshotDiffOut(BaseModel):
    """两快照之间的字段级差异。"""

    from_version: int
    to_version: int
    changes: dict


class CaseWorkflowRequest(BaseModel):
    comment: str | None = None


class RunTriggerRequest(BaseModel):
    env_id: int | None = None
    extra_vars: dict = Field(default_factory=dict)


class StepResultOut(BaseModel):
    id: int
    step_index: int
    name: str
    status: RunStatus
    duration_ms: int | None
    request_data: dict | None
    response_data: dict | None
    screenshot_url: str | None
    error_message: str | None
    healing_suggestion: str | None = None
    healing_status: str | None = None
    healing_at: datetime | None = None
    healing_feedback: str | None = None
    healing_feedback_at: datetime | None = None

    model_config = {"from_attributes": True}


class HealingFeedbackRequest(BaseModel):
    """对 done 态的 step 诊断建议给反馈。"""

    action: Literal["adopted", "rejected"]


class FailureDiagnosisOut(BaseModel):
    status: Literal["done", "skipped"]
    source: Literal["llm", "rule", "rule_fallback"]
    summary: str
    at: str
    failed_step_count: int
    screenshot_count: int
    repair_suggestions: list[dict] = Field(default_factory=list)
    error_samples: list[dict] = Field(default_factory=list)


class TestRunListItem(BaseModel):
    id: int
    case_id: int
    triggered_by: int
    trace_id: str | None = None
    status: RunStatus
    environment: str | None
    duration_ms: int | None
    error_message: str | None
    result_summary: dict
    iteration_index: int | None = None
    parent_run_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TestRunOut(BaseModel):
    id: int
    case_id: int
    triggered_by: int
    trace_id: str | None = None
    status: RunStatus
    environment: str | None
    duration_ms: int | None
    error_message: str | None
    result_summary: dict
    iteration_index: int | None = None
    iteration_data: dict | None = None
    parent_run_id: int | None = None
    created_at: datetime
    steps: list[StepResultOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PaginatedRunsOut(BaseModel):
    items: list[TestRunListItem]
    total: int
    page: int
    page_size: int


class RunCursorPage(BaseModel):
    items: list[TestRunListItem]
    next_cursor: str | None = None
    has_more: bool = False


class CaseBatchDeleteIn(BaseModel):
    case_ids: list[int] = Field(min_length=1, max_length=500)


class CaseBatchMoveIn(BaseModel):
    case_ids: list[int] = Field(min_length=1, max_length=500)
    target_module_id: int


class CaseBatchOpOut(BaseModel):
    requested: int
    processed: int
    skipped_ids: list[int] = Field(default_factory=list)


class CaseBatchImportOut(BaseModel):
    imported: int
    skipped_count: int = 0
    target_module_id: int
    created_ids: list[int] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CaseBatchImportPreviewItem(BaseModel):
    row: int
    name: str
    case_type: str
    priority: str
    step_count: int = 0


class CaseBatchImportPreviewOut(BaseModel):
    total: int
    valid_count: int
    invalid_count: int
    preview_cases: list[CaseBatchImportPreviewItem] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
