"""iOS device and IPA assets used by the Appium execution boundary."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class IosDeviceStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    busy = "busy"


class IosDevice(Base, TimestampMixin):
    """A physical iPhone or simulator exposed through an Appium/XCUITest worker."""

    __tablename__ = "ios_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    udid: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    model: Mapped[str | None] = mapped_column(String(128))
    platform_version: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[IosDeviceStatus] = mapped_column(Enum(IosDeviceStatus), default=IosDeviceStatus.offline)
    appium_server_url: Mapped[str] = mapped_column(String(512), nullable=False, default="http://127.0.0.1:4723")
    wda_local_port: Mapped[int | None] = mapped_column(Integer)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    port: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    leases = relationship("IosDeviceLease", back_populates="device", cascade="all, delete-orphan")


class IosDeviceLease(Base):
    """Database lease for an iOS device, mirroring Android device isolation."""

    __tablename__ = "ios_device_leases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("ios_devices.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    lease_token: Mapped[str] = mapped_column(String(96), unique=True, nullable=False, index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    owner_label: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    device = relationship("IosDevice", back_populates="leases")
    owner = relationship("User")


class IosApp(Base, TimestampMixin):
    """Project-scoped IPA asset; signing metadata is descriptive and never stored as a secret."""

    __tablename__ = "ios_apps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    bundle_id: Mapped[str | None] = mapped_column(String(256))
    version_name: Mapped[str | None] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    signing_identity: Mapped[str | None] = mapped_column(String(256))
    provisioning_profile: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    project = relationship("Project")
