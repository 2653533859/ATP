"""远程设备接入点（Device Agent）数据模型。

支持 B 机上的设备接入助手通过反向 WebSocket 隧道连接，
将远端插着的物理 Android 设备的 USB 端口映射至本地 127.0.0.1:<tunnel_port>。
"""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class RemoteAgent(Base, TimestampMixin):
    __tablename__ = "remote_agents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="OFFLINE")  # ONLINE | OFFLINE
    agent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    os_info: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    devices: Mapped[list["RemoteAgentDevice"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class RemoteAgentDevice(Base, TimestampMixin):
    __tablename__ = "remote_agent_devices"
    __table_args__ = (UniqueConstraint("agent_id", "usb_serial", name="uq_remote_agent_device_agent_serial"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("remote_agents.id", ondelete="CASCADE"), index=True)
    usb_serial: Mapped[str] = mapped_column(String(128), index=True)
    tunnel_port: Mapped[int] = mapped_column(Integer, unique=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped["RemoteAgent"] = relationship(back_populates="devices")
