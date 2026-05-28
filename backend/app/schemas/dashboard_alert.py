from datetime import datetime

from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.dashboard_alert import DashboardAlertMetric, DashboardAlertOperator


class DashboardAlertRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    project_id: int = Field(gt=0)
    metric: DashboardAlertMetric
    op: DashboardAlertOperator
    threshold: float
    window_minutes: int = Field(default=60, ge=1, le=10080)
    suppress_minutes: int = Field(
        default=settings.DASHBOARD_ALERT_DEFAULT_SUPPRESS_MIN,
        ge=1,
        le=10080,
    )
    notification_config_id: int | None = Field(default=None, gt=0)
    enabled: bool = True


class DashboardAlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    metric: DashboardAlertMetric | None = None
    op: DashboardAlertOperator | None = None
    threshold: float | None = None
    window_minutes: int | None = Field(default=None, ge=1, le=10080)
    suppress_minutes: int | None = Field(default=None, ge=1, le=10080)
    notification_config_id: int | None = Field(default=None, gt=0)
    enabled: bool | None = None


class DashboardAlertRuleOut(BaseModel):
    id: int
    name: str
    project_id: int
    metric: DashboardAlertMetric
    op: DashboardAlertOperator
    threshold: float
    window_minutes: int
    suppress_minutes: int
    notification_config_id: int | None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardAlertEventCreate(BaseModel):
    rule_id: int = Field(gt=0)
    actual_value: float
    triggered_at: datetime | None = None
    snoozed_until: datetime | None = None


class DashboardAlertEventOut(BaseModel):
    id: int
    rule_id: int
    triggered_at: datetime
    actual_value: float
    snoozed_until: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
