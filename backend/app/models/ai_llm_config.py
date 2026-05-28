from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AILLMConfig(Base, TimestampMixin):
    """AI 大语言模型配置：后台录入的 provider/api_key/endpoint/model_name。

    api_key_encrypted 使用 Fernet 对称加密存储；项目通过
    Project.ai_llm_config_id 关联使用哪一份配置。
    """

    __tablename__ = "ai_llm_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(256))
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    default_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text)
