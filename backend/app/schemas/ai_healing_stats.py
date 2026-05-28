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


class AIHealingStatsOut(BaseModel):
    total_feedback_count: int
    adopted_count: int
    rejected_count: int
    adopted_rate: float
    high_quality_example_count: int
    by_case_type: list[AIHealingCaseTypeStat]
    top_error_fingerprints: list[AIHealingTopFingerprint]
    recent_trend: list[AIHealingTrendItem]
