import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Enum, ForeignKey, DateTime, JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func

from app.models.base import Base, TimestampMixin


class TaskType(str, enum.Enum):
    performance = "performance"
    stability = "stability"
    fluency = "fluency"


class SourceType(str, enum.Enum):
    apk_only = "apk_only"
    case = "case"
    suite = "suite"
    monkey = "monkey"


class DeviceScopeType(str, enum.Enum):
    single_device = "single_device"
    device_group = "device_group"
    manual_pick = "manual_pick"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class TriggerType(str, enum.Enum):
    manual = "manual"
    schedule = "schedule"
    webhook = "webhook"


class IncidentType(str, enum.Enum):
    crash = "crash"
    anr = "anr"
    fatal_log = "fatal_log"
    watchdog = "watchdog"


class MetricType(str, enum.Enum):
    cpu_pct = "cpu_pct"
    mem_mb = "mem_mb"
    fps = "fps"
    jank_count = "jank_count"
    frame_time_ms = "frame_time_ms"
    battery_pct = "battery_pct"
    temperature_c = "temperature_c"
    network_rx_kb = "network_rx_kb"
    network_tx_kb = "network_tx_kb"


class ArtifactType(str, enum.Enum):
    csv = "csv"
    json = "json"
    screenshot = "screenshot"
    raw_log = "raw_log"
    trace = "trace"


class MobileSpecialTask(Base, TimestampMixin):
    __tablename__ = "mobile_special_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False, default=SourceType.apk_only)
    source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    device_scope_type: Mapped[DeviceScopeType] = mapped_column(Enum(DeviceScopeType), nullable=False)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    device_group_tag: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    apk_id: Mapped[Optional[int]] = mapped_column(ForeignKey("apks.id", ondelete="SET NULL"), nullable=True)
    app_package: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    schedule_enabled: Mapped[bool] = mapped_column(default=False)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="mobile_special_tasks")
    device = relationship("Device")
    apk = relationship("Apk")
    runs = relationship("MobileSpecialRun", back_populates="task", cascade="all, delete-orphan")


class MobileSpecialRun(Base, TimestampMixin):
    __tablename__ = "mobile_special_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("mobile_special_tasks.id", ondelete="CASCADE"), nullable=False)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), nullable=False, default=RunStatus.pending)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    device_serial: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    apk_id: Mapped[Optional[int]] = mapped_column(ForeignKey("apks.id", ondelete="SET NULL"), nullable=True)
    app_package: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    trigger_type: Mapped[TriggerType] = mapped_column(Enum(TriggerType), nullable=False, default=TriggerType.manual)
    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    task = relationship("MobileSpecialTask", back_populates="runs")
    device = relationship("Device")
    apk = relationship("Apk")
    samples = relationship("MobileMetricSample", back_populates="run", cascade="all, delete-orphan")
    incidents = relationship("MobileIncident", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("MobileRunArtifact", back_populates="run", cascade="all, delete-orphan")


class MobileMetricSample(Base):
    __tablename__ = "mobile_metric_samples"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("mobile_special_runs.id", ondelete="CASCADE"), nullable=False)
    sample_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_type: Mapped[MetricType] = mapped_column(Enum(MetricType), nullable=False)
    metric_value: Mapped[float] = mapped_column(nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    extra_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")

    # Relationships
    run = relationship("MobileSpecialRun", back_populates="samples")


class MobileIncident(Base):
    __tablename__ = "mobile_incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("mobile_special_runs.id", ondelete="CASCADE"), nullable=False)
    incident_type: Mapped[IncidentType] = mapped_column(Enum(IncidentType), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    process_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    thread_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Relationships
    run = relationship("MobileSpecialRun", back_populates="incidents")


class MobileRunArtifact(Base):
    __tablename__ = "mobile_run_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("mobile_special_runs.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    run = relationship("MobileSpecialRun", back_populates="artifacts")
