import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.case import RunStatus
from app.services.ai_healing_stats import _date_key, _is_ai_healing_regression, _is_success_status, _rate


def test_rate_returns_percentage_with_two_decimals():
    assert _rate(2, 3) == 66.67
    assert _rate(0, 0) == 0.0


def test_date_key_handles_date_like_and_strings():
    class DateLike:
        def isoformat(self):
            return "2026-05-28"

    assert _date_key(DateLike()) == "2026-05-28"
    assert _date_key("2026-05-28") == "2026-05-28"


def test_ai_healing_regression_detector_uses_result_summary_flag():
    class Run:
        result_summary = {"triggered_by_ai_healing_patch": True}

    assert _is_ai_healing_regression(Run()) is True

    Run.result_summary = {"triggered_by_ai_healing_patch": False}
    assert _is_ai_healing_regression(Run()) is False

    Run.result_summary = None
    assert _is_ai_healing_regression(Run()) is False


def test_success_status_accepts_passed_and_success_values():
    assert _is_success_status(RunStatus.passed) is True
    assert _is_success_status("success") is True
    assert _is_success_status(RunStatus.failed) is False
