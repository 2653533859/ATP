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
