"""Prevent SQLite from reusing execution IDs after a case is deleted."""

from sqlalchemy import event

from app.core.config import settings
from app.models.case import TestRun
from app.models.mobile_special import MobileSpecialRun
from app.models.performance import PerformanceRun
from app.models.plan import PlanRun
from app.models.suite import SuiteRun

_installed = False


def install_local_run_id_allocator() -> None:
    global _installed
    if _installed:
        return

    def allocate(_mapper, connection, target) -> None:
        if settings.ATP_LOCAL_MODE and connection.dialect.name == "sqlite" and target.id is None:
            result = connection.exec_driver_sql("INSERT INTO local_run_ids DEFAULT VALUES")
            allocated_id = int(result.lastrowid)
            highest = connection.exec_driver_sql(
                "SELECT MAX(value) FROM ("
                "SELECT COALESCE(MAX(id), 0) AS value FROM test_runs UNION ALL "
                "SELECT COALESCE(MAX(id), 0) FROM suite_runs UNION ALL "
                "SELECT COALESCE(MAX(id), 0) FROM plan_runs UNION ALL "
                "SELECT COALESCE(MAX(id), 0) FROM performance_runs UNION ALL "
                "SELECT COALESCE(MAX(id), 0) FROM mobile_special_runs)"
            ).scalar_one()
            if highest and allocated_id <= highest:
                next_safe_id = int(highest) + 1
                connection.exec_driver_sql("INSERT OR REPLACE INTO local_run_ids(id) VALUES (?)", (next_safe_id,))
                allocated_id = next_safe_id
            target.id = allocated_id

    for model in (TestRun, SuiteRun, PlanRun, MobileSpecialRun, PerformanceRun):
        event.listen(model, "before_insert", allocate)
    _installed = True
