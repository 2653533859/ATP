from pydantic import BaseModel


class OverviewOut(BaseModel):
    total_cases: int
    total_runs: int
    pass_rate: float
    recent_runs_7d: int


class PassRateTrendItem(BaseModel):
    date: str
    total: int
    passed: int
    rate: float


class DurationTrendItem(BaseModel):
    date: str
    avg_duration_ms: float
    max_duration_ms: int
    run_count: int


class FailureTopItem(BaseModel):
    case_id: int
    project_id: int
    module_id: int
    case_name: str
    case_type: str
    failure_count: int
