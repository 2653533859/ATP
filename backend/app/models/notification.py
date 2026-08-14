import enum
from sqlalchemy import String, ForeignKey, JSON, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class NotifyChannel(str, enum.Enum):
    email = "email"
    wechat = "wechat"
    dingtalk = "dingtalk"


class NotificationConfig(Base, TimestampMixin):
    __tablename__ = "notification_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[NotifyChannel] = mapped_column(Enum(NotifyChannel), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 渠道配置 JSON，结构因渠道而异：
    # email:    {"recipients": ["a@b.com"], "subject_prefix": "[ATP]"}
    # wechat:   {"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."}
    # dingtalk: {"webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=...", "secret": "..."}
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="notifications")  # noqa: F821


class NotificationDelivery(Base, TimestampMixin):
    """一次通知渠道投递的脱敏结果。"""

    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[NotifyChannel] = mapped_column(Enum(NotifyChannel), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(default=1)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
