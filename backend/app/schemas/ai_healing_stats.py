from pydantic import BaseModel


class AIHealingCaseTypeStat(BaseModel):
    case_type: str
    total_count: int
    adopted_count: int
    rejected_count: int
    adopted_rate: float


class AIHealingTopFingerprint(BaseModel):
    error_fingerprint: str
    case_type: str
    total_count: int
    adopted_count: int
    rejected_count: int
    adopted_rate: float


class AIHealingTrendItem(BaseModel):
    date: str
    total_count: int
    adopted_count: int
    rejected_count: int
    adopted_rate: float


class AIHealingProductionFeedback(BaseModel):
    regression_triggered_count: int
    regression_success_count: int
    regression_success_rate: float
    latest_feedback_aggregated_at: str | None = None


class AIHealingStatsOut(BaseModel):
    total_feedback_count: int
    adopted_count: int
    rejected_count: int
    adopted_rate: float
    high_quality_example_count: int
    by_case_type: list[AIHealingCaseTypeStat]
    top_error_fingerprints: list[AIHealingTopFingerprint]
    recent_trend: list[AIHealingTrendItem]
    production_feedback: AIHealingProductionFeedback
