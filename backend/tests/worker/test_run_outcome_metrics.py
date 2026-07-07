from enum import Enum
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core import metrics
from app.worker import tasks


class _Status(str, Enum):
    passed = "passed"
    running = "running"


class _Metric:
    def __init__(self):
        self.labels_seen: list[dict[str, str]] = []
        self.inc_count = 0

    def labels(self, **kwargs):
        self.labels_seen.append(kwargs)
        return self

    def inc(self):
        self.inc_count += 1


def test_record_run_outcome_emits_terminal_status_metric(monkeypatch):
    metric = _Metric()
    monkeypatch.setattr(metrics, "RUN_OUTCOMES", metric)

    tasks._record_run_outcome("plan", _Status.passed)

    assert metric.labels_seen == [{"entity_type": "plan", "status": "passed"}]
    assert metric.inc_count == 1


def test_record_run_outcome_ignores_non_terminal_status(monkeypatch):
    metric = _Metric()
    monkeypatch.setattr(metrics, "RUN_OUTCOMES", metric)

    tasks._record_run_outcome("case", _Status.running)

    assert metric.labels_seen == []
    assert metric.inc_count == 0
