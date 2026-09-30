"""Prevent SQLite from reusing execution IDs after a case is deleted."""

from sqlalchemy import event

from app.core.config import settings
from app.models.case import TestRun
from app.models.mobile_special import MobileSpecialRun
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
            target.id = int(result.lastrowid)

    for model in (TestRun, SuiteRun, PlanRun, MobileSpecialRun):
        event.listen(model, "before_insert", allocate)
    _installed = True
