from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


LLMProvider = Literal["deepseek", "claude", "openai", "openai_compatible", "qwen", "ollama"]


class AILLMConfigOut(BaseModel):
    """配置详情（不返回 api_key，仅返回 has_api_key 标记）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: LLMProvider
    endpoint: str | None = None
    model_name: str
    default_params: dict = Field(default_factory=dict)
    enabled: bool
    supports_vision: bool = False
    description: str | None = None
    has_api_key: bool = True
    created_at: datetime
    updated_at: datetime


class AILLMConfigCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    provider: LLMProvider
    api_key: str = Field(default="", max_length=512)
    endpoint: str | None = Field(default=None, max_length=256)
    model_name: str = Field(min_length=1, max_length=64)
    default_params: dict = Field(default_factory=dict)
    enabled: bool = True
    supports_vision: bool = False
    description: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_api_key(self):
        if self.provider != "ollama" and not self.api_key.strip():
            raise ValueError("该供应商必须填写 API Key")
        if self.provider == "openai_compatible" and not (self.endpoint or "").strip():
            raise ValueError("OpenAI 兼容供应商必须填写 Endpoint")
        return self


class AILLMConfigUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    provider: LLMProvider | None = None
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    endpoint: str | None = Field(default=None, max_length=256)
    model_name: str | None = Field(default=None, min_length=1, max_length=64)
    default_params: dict | None = None
    enabled: bool | None = None
    supports_vision: bool | None = None
    description: str | None = Field(default=None, max_length=2048)


class AILLMModelDiscoveryIn(BaseModel):
    config_id: int | None = None
    provider: LLMProvider
    api_key: str | None = Field(default=None, max_length=512)
    endpoint: str | None = Field(default=None, max_length=256)


class AILLMConnectionTestIn(BaseModel):
    config_id: int | None = None
    provider: LLMProvider | None = None
    api_key: str | None = Field(default=None, max_length=512)
    endpoint: str | None = Field(default=None, max_length=256)
    model_name: str | None = Field(default=None, min_length=1, max_length=64)
    default_params: dict | None = None


class AILLMModelOptionOut(BaseModel):
    id: str
    label: str
    owned_by: str | None = None
    supports_vision: bool | None = None
    supports_reasoning: bool | None = None
    capability_source: str = "unknown"
    capabilities: list[str] = Field(default_factory=list)


class AILLMModelDiscoveryOut(BaseModel):
    provider: LLMProvider
    endpoint: str
    models: list[AILLMModelOptionOut] = Field(default_factory=list)


class AILLMConnectionTestOut(BaseModel):
    provider: LLMProvider
    model_name: str
    latency_ms: float
    response_received: bool = True
    message: str
