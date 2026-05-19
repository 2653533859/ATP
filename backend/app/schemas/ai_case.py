"""AI 用例生成相关 schemas。

两个核心场景：
  1. parse-schema：上传/粘贴 OpenAPI / Postman / cURL 文本，返回结构化接口清单
  2. generate：根据接口清单 + 用户需求，调用 LLM 生成用例草稿
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.models.case import CaseType
from app.schemas.case import CasePriority, CaseLevel


SchemaSourceType = Literal["openapi", "postman", "curl"]


class AIParseSchemaIn(BaseModel):
    """解析 API 描述文件，返回标准化接口清单。"""

    source_type: SchemaSourceType
    content: str = Field(min_length=1, max_length=2_000_000)


class AIEndpointParameter(BaseModel):
    name: str
    location: Literal["path", "query", "header", "body"]
    required: bool = False
    schema_type: str | None = None
    description: str | None = None
    example: object | None = None


class AIEndpointSummary(BaseModel):
    """单个接口的归一化描述。"""

    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    operation_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    parameters: list[AIEndpointParameter] = Field(default_factory=list)
    request_body_example: object | None = None
    response_example: object | None = None


class AIParseSchemaOut(BaseModel):
    endpoints: list[AIEndpointSummary]
    warnings: list[str] = Field(default_factory=list)


class AICaseGenerateIn(BaseModel):
    """根据接口 + 业务需求生成用例草稿。"""

    project_id: int
    module_id: int
    endpoints: list[AIEndpointSummary] = Field(default_factory=list, max_length=20)
    user_requirement: str = Field(default="", max_length=4000)
    case_type: CaseType = CaseType.api
    priority: CasePriority = "P2"
    case_level: CaseLevel = "regression"
    max_cases: int = Field(default=5, ge=1, le=20)


class AICaseStepDraft(BaseModel):
    action: str
    test_data: str | None = None
    expected_result: str | None = None
    is_key_step: bool = False
    remarks: str | None = None


class AICaseDraft(BaseModel):
    """单条用例草稿（前端用于填入 CaseFormDrawer 后再保存）。"""

    name: str
    summary: str | None = None
    description: str | None = None
    case_type: CaseType
    priority: CasePriority = "P2"
    case_level: CaseLevel = "regression"
    tags: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    steps: list[AICaseStepDraft] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)


class AICaseGenerateOut(BaseModel):
    project_id: int
    module_id: int
    drafts: list[AICaseDraft]
    raw_response: str | None = None
    warnings: list[str] = Field(default_factory=list)
