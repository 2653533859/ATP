"""Regression coverage for the project report center contract."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import reports
from app.models.bootstrap import load_all_models
from app.models.case import CaseType, RunStatus
from app.schemas.reports import ReportRunSnapshot

load_all_models()


class _Result:
    def __init__(self, *, scalar=None, one=None, rows=None, scalar_rows=None):
        self.scalar_value = scalar
        self.one_value = one
        self.rows = rows or []
        self.scalar_rows = scalar_rows or []

    def scalar_one(self):
        return self.scalar_value

    def one(self):
        return self.one_value

    def all(self):
        return self.rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self.scalar_rows)


class _FakeDB:
    def __init__(self, results):
        self.results = results
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results[len(self.statements) - 1]


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _admin():
    return SimpleNamespace(id=1, role="admin", username="admin")


def test_quality_score_is_transparent_and_empty_runs_are_zero():
    assert reports._quality_score(80, 60, 1, 10, 4) == (76.5, 90.0)
    assert reports._quality_score(0, 0, 0, 10, 0) == (0.0, 100.0)


def test_safe_error_redacts_credentials():
    assert reports._safe_error("Authorization: Bearer secret-token") == "Authorization=[REDACTED]"


def test_report_overview_returns_coverage_quality_trend_and_recent_runs(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(reports, "assert_project_access", no_access)
    monkeypatch.setattr(reports, "scope_to_visible_projects", lambda statement, *_args: statement)
    monkeypatch.setattr(reports, "_since", lambda _days: NOW)

    recent_run = SimpleNamespace(
        id=44,
        case_id=9,
        status=RunStatus.passed,
        duration_ms=1200,
        error_message=None,
        created_at=NOW,
    )
    db = _FakeDB(
        [
            _Result(scalar=10),
            _Result(
                one=SimpleNamespace(
                    total=8,
                    passed=6,
                    failed=1,
                    error=1,
                    avg_duration=1250,
                    executed_cases=7,
                )
            ),
            _Result(scalar=1),
            _Result(rows=[SimpleNamespace(date="2026-08-24", total=8, passed=6, failed=1, error=1, avg_duration=1250)]),
            _Result(rows=[(recent_run, "登录用例", CaseType.api, 3)]),
        ]
    )

    result = asyncio.run(reports.get_report_overview(project_id=3, days=30, recent_limit=20, db=db, user=_admin()))

    assert result.total_cases == 10
    assert result.executed_cases == 7
    assert result.coverage_rate == 70.0
    assert result.pass_rate == 75.0
    assert result.open_defects == 1
    assert result.trend[0].failed == 1
    assert result.recent_runs[0].case_name == "登录用例"
    assert result.quality_score == 76.0


def test_compare_report_runs_rejects_same_run_and_detects_regression(monkeypatch):
    baseline = ReportRunSnapshot(
        id=1,
        project_id=3,
        case_id=9,
        case_name="登录用例",
        case_type="api",
        status="passed",
        duration_ms=1000,
        total_steps=4,
        passed_steps=4,
        failed_steps=0,
        error_steps=0,
        created_at=NOW,
    )
    current = baseline.model_copy(
        update={"id": 2, "status": "failed", "duration_ms": 1400, "failed_steps": 1, "passed_steps": 3}
    )

    with pytest.raises(HTTPException) as same_exc:
        asyncio.run(
            reports.compare_report_runs(
                baseline_run_id=1,
                current_run_id=1,
                db=object(),
                user=_admin(),
            )
        )
    assert same_exc.value.status_code == 422

    async def fake_snapshot(_db, _user, run_id):
        return baseline if run_id == 1 else current

    monkeypatch.setattr(reports, "_load_run_snapshot", fake_snapshot)
    result = asyncio.run(
        reports.compare_report_runs(
            baseline_run_id=1,
            current_run_id=2,
            db=object(),
            user=_admin(),
        )
    )
    assert result.has_regression is True
    assert result.metrics[0].delta == 400.0
    assert result.metrics[2].delta == 1.0


def test_compare_report_runs_rejects_different_cases(monkeypatch):
    baseline = ReportRunSnapshot(
        id=1,
        project_id=3,
        case_id=9,
        case_name="A",
        case_type="api",
        status="passed",
        total_steps=1,
        passed_steps=1,
        failed_steps=0,
        error_steps=0,
        created_at=NOW,
    )
    current = baseline.model_copy(update={"id": 2, "case_id": 10})

    async def fake_snapshot(_db, _user, run_id):
        return baseline if run_id == 1 else current

    monkeypatch.setattr(reports, "_load_run_snapshot", fake_snapshot)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            reports.compare_report_runs(
                baseline_run_id=1,
                current_run_id=2,
                db=object(),
                user=_admin(),
            )
        )
    assert exc.value.status_code == 400
