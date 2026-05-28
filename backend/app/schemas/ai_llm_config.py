from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


LLMProvider = Literal["deepseek", "claude", "openai", "qwen", "ollama"]


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
    api_key: str = Field(min_length=1, max_length=512)
    endpoint: str | None = Field(default=None, max_length=256)
    model_name: str = Field(min_length=1, max_length=64)
    default_params: dict = Field(default_factory=dict)
    enabled: bool = True
    supports_vision: bool = False
    description: str | None = Field(default=None, max_length=2048)


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
