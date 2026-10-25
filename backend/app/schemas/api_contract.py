from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.api_contract_asset import ApiContractAssetCompareIn


class ApiContractCompareIn(BaseModel):
    baseline: dict = Field(description="基线 OpenAPI/Swagger 或 JSON Schema")
    current: dict = Field(description="当前 OpenAPI/Swagger 或 JSON Schema")


class ApiContractChange(BaseModel):
    severity: Literal["breaking", "warning"]
    location: str
    message: str


class ApiContractCompareOut(BaseModel):
    compatible: bool
    breaking_changes: list[ApiContractChange] = Field(default_factory=list)
    warnings: list[ApiContractChange] = Field(default_factory=list)
    summary: str


class SpecCaseSyncIn(BaseModel):
    spec: dict = Field(description="新版 OpenAPI / Swagger 规范 JSON 字典")
    baseline: dict | None = Field(default=None, description="可选的旧版规格，用于发现仅在场景中引用的变更端点")
    default_module_id: int | None = Field(default=None, description="新增用例默认归属的模块编号 ID")


class SpecCaseDiff(BaseModel):
    endpoint: str
    change_type: Literal["addition", "modification", "deprecation"]
    case_id: int | None = None
    case_name: str | None = None
    details: list[str] = Field(default_factory=list)
    patch_payload: dict | None = None


class SpecScenarioImpact(BaseModel):
    scenario_id: int
    scenario_name: str
    step_index: int
    step_name: str
    endpoint: str
    source_case_id: int | None = None
    review_reason: str


class SpecCaseSyncOut(BaseModel):
    total_spec_endpoints: int
    total_cases: int
    additions_count: int
    modifications_count: int
    deprecations_count: int
    diffs: list[SpecCaseDiff] = Field(default_factory=list)
    draft_patches: list[dict] = Field(default_factory=list)
    scenario_impacts: list[SpecScenarioImpact] = Field(default_factory=list)
