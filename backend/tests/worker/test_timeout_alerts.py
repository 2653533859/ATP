import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.worker import timeout_alerts


class _FakeSoftTimeout(Exception):
    pass


# 仅靠类名判断，构造同名异常即可命中告警分支
_FakeSoftTimeout.__name__ = "SoftTimeLimitExceeded"


def test_soft_timeout_emits_warning(caplog):
    with caplog.at_level(logging.WARNING):
        timeout_alerts.on_task_failure("my_task", "task-123", _FakeSoftTimeout("timeout"))
    assert "celery_soft_timeout" in caplog.text
    assert "my_task" in caplog.text
    assert "task-123" in caplog.text


def test_non_timeout_failure_ignored(caplog):
    with caplog.at_level(logging.WARNING):
        timeout_alerts.on_task_failure("my_task", "task-1", ValueError("oops"))
    assert "celery_soft_timeout" not in caplog.text


def test_missing_exception_ignored(caplog):
    with caplog.at_level(logging.WARNING):
        timeout_alerts.on_task_failure("my_task", "task-1", None)
    assert "celery_soft_timeout" not in caplog.text


def test_hard_timeout_emits_warning(caplog):
    with caplog.at_level(logging.WARNING):
        timeout_alerts.on_task_revoked(
            "my_task", "task-9", terminated=True, signum=15, expired=False
        )
    assert "celery_hard_timeout" in caplog.text
    assert "signum=15" in caplog.text


def test_revoke_when_expired_not_logged_as_timeout(caplog):
    with caplog.at_level(logging.WARNING):
        timeout_alerts.on_task_revoked(
            "my_task", "task-9", terminated=True, signum=None, expired=True
        )
    assert "celery_hard_timeout" not in caplog.text


def test_normal_revoke_not_logged_as_timeout(caplog):
    with caplog.at_level(logging.WARNING):
        timeout_alerts.on_task_revoked(
            "my_task", "task-9", terminated=False, signum=None, expired=False
        )
    assert "celery_hard_timeout" not in caplog.text
