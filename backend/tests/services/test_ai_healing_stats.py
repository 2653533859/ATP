import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ai_healing_stats import _date_key, _rate


def test_rate_returns_percentage_with_two_decimals():
    assert _rate(2, 3) == 66.67
    assert _rate(0, 0) == 0.0


def test_date_key_handles_date_like_and_strings():
    class DateLike:
        def isoformat(self):
            return "2026-05-28"

    assert _date_key(DateLike()) == "2026-05-28"
    assert _date_key("2026-05-28") == "2026-05-28"
