import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_minio = sys.modules.setdefault("app.core.minio_client", types.SimpleNamespace())
_minio.list_objects = lambda prefix: []
_minio.delete_file = lambda object_name: None

from app.models.bootstrap import load_all_models
from app.services import run_retention

# 本文件的断言会 str() 真实 SQLAlchemy 语句（JOIN TestPlan / Module / MobileSpecialTask），
# 这会触发 Project mapper 配置。单独运行本文件时若不预先注册全部模型，
# Project.relationship('NotificationConfig') 无法解析而报 InvalidRequestError。
load_all_models()


class _FakeResult:
    def __init__(self, all_rows=(), scalar_value=None):
        self._rows = list(all_rows)
        self._scalar = scalar_value

    def all(self):
        return self._rows

    def scalar(self):
        return self._scalar


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.commits = 0
        self.statements = []

    def execute(self, stmt):
        self.statements.append(stmt)
        if not self._responses:
            return _FakeResult([])
        return self._responses.pop(0)

    def commit(self):
        self.commits += 1


def test_preview_returns_counts_without_deleting():
    """5 个 count + 3 个 sample id 查询；无 delete 无 commit。"""
    fake_session = _FakeSession(
        responses=[
            _FakeResult(scalar_value=3),  # plan count
            _FakeResult(scalar_value=5),  # suite count
            _FakeResult(scalar_value=7),  # test count
            _FakeResult(scalar_value=2),  # mobile count
            _FakeResult(scalar_value=4),  # performance count
            _FakeResult(all_rows=[]),  # test sample ids -> empty
            _FakeResult(all_rows=[]),  # mobile sample ids -> empty
            _FakeResult(all_rows=[]),  # performance sample ids -> empty
        ]
    )
    result = run_retention.preview_old_runs(fake_session, days=30, batch_size=10)

    assert result["plan_runs"] == 3
    assert result["suite_runs"] == 5
    assert result["test_runs"] == 7
    assert result["mobile_runs"] == 2
    assert result["performance_runs"] == 4
    assert result["retention_days"] == 30
    assert result["estimated_objects"] == 0
    assert result["estimated_objects_sampled"] is False
    assert fake_session.commits == 0
    # 5 个 count + 3 个 sample id 查询；空 sample 不执行对象查询
    assert len(fake_session.statements) == 8


def test_preview_estimates_objects_from_sample(monkeypatch):
    """非空 sample → 触发 screenshot/artifact 查询估算对象数。"""
    fake_session = _FakeSession(
        responses=[
            _FakeResult(scalar_value=1),  # plan count
            _FakeResult(scalar_value=1),  # suite count
            _FakeResult(scalar_value=2),  # test count
            _FakeResult(scalar_value=1),  # mobile count
            _FakeResult(scalar_value=1),  # performance count
            _FakeResult(all_rows=[(100,), (101,)]),  # test sample
            _FakeResult(all_rows=[(200,)]),  # mobile sample
            _FakeResult(all_rows=[]),  # performance sample
            # screenshot query for test sample
            _FakeResult(all_rows=[("screenshots/runs/100/a.png",), ("screenshots/runs/101/b.png",)]),
            # mobile artifact query
            _FakeResult(all_rows=[("artifacts/200/log.txt",)]),
            # mobile incident query
            _FakeResult(all_rows=[]),
        ]
    )
    # extract_object_name 默认能识别 raw object key
    result = run_retention.preview_old_runs(fake_session, days=30, batch_size=10)

    assert result["test_runs"] == 2
    assert result["estimated_objects"] >= 1  # 至少抽到一些对象
    assert result["estimated_objects_sampled"] is False


def test_preview_marks_object_count_as_sampled_when_candidates_exceed_batch_size():
    fake_session = _FakeSession(
        responses=[
            _FakeResult(scalar_value=0),
            _FakeResult(scalar_value=0),
            _FakeResult(scalar_value=11),
            _FakeResult(scalar_value=0),
            _FakeResult(scalar_value=0),
            _FakeResult(all_rows=[]),
            _FakeResult(all_rows=[]),
            _FakeResult(all_rows=[]),
        ]
    )

    result = run_retention.preview_old_runs(fake_session, days=30, batch_size=10)

    assert result["estimated_objects_sampled"] is True


def test_preview_can_exclude_project_overrides_with_the_cleanup_scope():
    fake_session = _FakeSession(
        responses=[
            _FakeResult(scalar_value=1),
            _FakeResult(scalar_value=2),
            _FakeResult(scalar_value=3),
            _FakeResult(scalar_value=4),
            _FakeResult(scalar_value=5),
            _FakeResult(all_rows=[]),
            _FakeResult(all_rows=[]),
            _FakeResult(all_rows=[]),
        ]
    )

    result = run_retention.preview_old_runs(fake_session, days=30, exclude_project_ids=[5, 6])

    assert result["plan_runs"] == 1
    assert all("NOT IN" in str(statement).upper() for statement in fake_session.statements[:4])


def test_performance_retention_selects_root_runs_and_collects_shard_reports():
    from datetime import datetime, timezone

    statement = run_retention._performance_run_ids_stmt(datetime.now(timezone.utc), project_id=7)
    sql = str(statement).upper()
    assert "PARENT_RUN_ID IS NULL" in sql
    assert "PROJECT_ID" in sql

    session = _FakeSession(
        responses=[
            _FakeResult(
                all_rows=[
                    ("performance/runs/10/summary.json",),
                    ("performance/runs/11/summary.json",),
                    ("performance/runs/10/summary.json",),
                ]
            )
        ]
    )
    assert run_retention._collect_performance_run_objects(session, [10]) == [
        "performance/runs/10/summary.json",
        "performance/runs/11/summary.json",
    ]


def test_execute_with_empty_results_is_noop():
    fake_session = _FakeSession(
        responses=[
            _FakeResult(all_rows=[]),  # override projects -> none
            _FakeResult(all_rows=[]),  # plan select
            _FakeResult(all_rows=[]),  # suite select
            _FakeResult(all_rows=[]),  # test select
            _FakeResult(all_rows=[]),  # mobile select
            _FakeResult(all_rows=[]),  # performance select
        ]
    )
    result = run_retention.execute_old_runs_cleanup(fake_session, days=30, batch_size=10)

    assert result["plan_runs"] == 0
    assert result["suite_runs"] == 0
    assert result["test_runs"] == 0
    assert result["mobile_runs"] == 0
    assert result["deleted_objects"] == 0
    assert result["retention_days"] == 30
    assert result["projects"] == []
    assert fake_session.commits == 0


def test_execute_processes_simple_batch():
    """plan_runs 有 2 条（< batch_size），其他空。应删除 2 条 + 1 次 commit。"""
    fake_session = _FakeSession(
        responses=[
            _FakeResult(all_rows=[]),  # override projects -> none
            _FakeResult(all_rows=[(1,), (2,)]),  # plan select -> 2 ids
            _FakeResult(all_rows=[]),  # plan delete (Result unused but pop'd)
            _FakeResult(all_rows=[]),  # suite select empty
            _FakeResult(all_rows=[]),  # test select empty
            _FakeResult(all_rows=[]),  # mobile select empty
            _FakeResult(all_rows=[]),  # performance select empty
        ]
    )
    result = run_retention.execute_old_runs_cleanup(fake_session, days=30, batch_size=10)

    assert result["plan_runs"] == 2
    assert fake_session.commits == 1


def test_batched_cleanup_commits_database_delete_before_minio_delete(monkeypatch):
    """数据库提交成功后才删除附件，避免提交失败造成不可恢复的引用丢失。"""

    from sqlalchemy import select

    from app.models.plan import PlanRun

    events: list[object] = []

    class _BatchSession:
        def __init__(self):
            self.responses = [_FakeResult(all_rows=[(1,), (2,)]), _FakeResult()]

        def execute(self, _statement):
            return self.responses.pop(0)

        def commit(self):
            events.append("commit")

    monkeypatch.setattr(
        run_retention,
        "_delete_minio_objects",
        lambda names: events.append(("minio", names)) or len(names),
    )

    deleted_runs, deleted_objects = run_retention._batched_delete_runs(
        _BatchSession(),
        PlanRun,
        select(PlanRun.id),
        batch_size=10,
        collect_objects=lambda _session, _ids: ["reports/run-1.html"],
    )

    assert (deleted_runs, deleted_objects) == (2, 1)
    assert events == ["commit", ("minio", ["reports/run-1.html"])]


def test_batched_cleanup_keeps_minio_object_when_database_commit_fails(monkeypatch):
    from sqlalchemy import select

    from app.models.plan import PlanRun

    minio_deletes: list[list[str]] = []

    class _FailingBatchSession:
        def __init__(self):
            self.responses = [_FakeResult(all_rows=[(1,)]), _FakeResult()]

        def execute(self, _statement):
            return self.responses.pop(0)

        def commit(self):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(run_retention, "_delete_minio_objects", lambda names: minio_deletes.append(names) or len(names))

    with pytest.raises(RuntimeError, match="database unavailable"):
        run_retention._batched_delete_runs(
            _FailingBatchSession(),
            PlanRun,
            select(PlanRun.id),
            batch_size=10,
            collect_objects=lambda _session, _ids: ["reports/run-1.html"],
        )

    assert minio_deletes == []


def test_batched_cleanup_deletes_performance_root_and_shard_reports_after_commit(monkeypatch):
    from sqlalchemy import select

    from app.models.performance import PerformanceRun

    events: list[object] = []

    class _PerformanceBatchSession:
        def __init__(self):
            self.responses = [
                _FakeResult(all_rows=[(10,)]),
                _FakeResult(
                    all_rows=[
                        ("performance/runs/10/summary.json",),
                        ("performance/runs/11/summary.json",),
                        ("performance/runs/10/summary.json",),
                    ]
                ),
                _FakeResult(),
            ]

        def execute(self, _statement):
            return self.responses.pop(0)

        def commit(self):
            events.append("commit")

    monkeypatch.setattr(
        run_retention,
        "_delete_minio_objects",
        lambda names: events.append(("minio", names)) or len(names),
    )

    deleted_runs, deleted_objects = run_retention._batched_delete_runs(
        _PerformanceBatchSession(),
        PerformanceRun,
        select(PerformanceRun.id),
        batch_size=10,
        collect_objects=run_retention._collect_performance_run_objects,
    )

    assert (deleted_runs, deleted_objects) == (1, 2)
    assert events == [
        "commit",
        ("minio", ["performance/runs/10/summary.json", "performance/runs/11/summary.json"]),
    ]


def test_execute_partitions_override_projects_from_global_pass():
    """override 项目按其天数单独清理；全局兜底 pass 的查询排除 override 项目。"""
    fake_session = _FakeSession(
        responses=[
            _FakeResult(all_rows=[(5, "alpha", 7)]),  # override projects
            # 项目 5 范围：plan 2 条 → delete；suite/test/mobile 空
            _FakeResult(all_rows=[(11,), (12,)]),  # plan select (project 5)
            _FakeResult(all_rows=[]),  # plan delete
            _FakeResult(all_rows=[]),  # suite select
            _FakeResult(all_rows=[]),  # test select
            _FakeResult(all_rows=[]),  # mobile select
            _FakeResult(all_rows=[]),  # performance select
            # 全局范围（排除项目 5）：plan 1 条，其余空
            _FakeResult(all_rows=[(31,)]),  # plan select (global, excl 5)
            _FakeResult(all_rows=[]),  # plan delete
            _FakeResult(all_rows=[]),  # suite select
            _FakeResult(all_rows=[]),  # test select
            _FakeResult(all_rows=[]),  # mobile select
            _FakeResult(all_rows=[]),  # performance select
        ]
    )
    result = run_retention.execute_old_runs_cleanup(fake_session, days=90, batch_size=10)

    # 汇总 = 项目 pass + 全局 pass
    assert result["plan_runs"] == 3
    assert result["projects"] == [
        {
            "project_id": 5,
            "project_name": "alpha",
            "retention_days": 7,
            "plan_runs": 2,
            "suite_runs": 0,
            "test_runs": 0,
            "mobile_runs": 0,
            "performance_runs": 0,
            "deleted_objects": 0,
        }
    ]
    assert fake_session.commits == 2

    # 项目 pass 的 plan 查询按 project_id 过滤；全局 pass 用 NOT IN 排除
    project_plan_sql = str(fake_session.statements[1])
    global_plan_sql = str(fake_session.statements[7])
    assert "project_id" in project_plan_sql and "JOIN" in project_plan_sql.upper()
    assert "NOT IN" in global_plan_sql.upper()


def test_execute_project_cutoff_uses_override_days():
    """项目 pass 的 cutoff 由 override 天数决定（7 天），全局 pass 用全局天数（90 天）。"""
    captured = []

    def fake_scope(_session, cutoff, _batch, **scope):
        captured.append((cutoff, scope))
        return {
            "plan_runs": 0,
            "suite_runs": 0,
            "test_runs": 0,
            "mobile_runs": 0,
            "performance_runs": 0,
            "deleted_objects": 0,
        }

    import unittest.mock as mock

    fake_session = _FakeSession(responses=[_FakeResult(all_rows=[(5, "alpha", 7)])])
    with mock.patch.object(run_retention, "_cleanup_scope", fake_scope):
        run_retention.execute_old_runs_cleanup(fake_session, days=90, batch_size=10)

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    project_cutoff, project_scope = captured[0]
    global_cutoff, global_scope = captured[1]
    assert 6.5 <= (now - project_cutoff).days + 0.5 <= 7.5 and project_scope == {"project_id": 5}
    assert 89.5 <= (now - global_cutoff).days + 0.5 <= 90.5 and global_scope == {"exclude_project_ids": [5]}


def test_cutoff_reflects_days_argument():
    """preview 的 cutoff = now - days；这里只验证差值大致正确。"""
    from datetime import datetime, timezone

    fake_session = _FakeSession(
        responses=[
            _FakeResult(scalar_value=0),
            _FakeResult(scalar_value=0),
            _FakeResult(scalar_value=0),
            _FakeResult(scalar_value=0),
            _FakeResult(scalar_value=0),
            _FakeResult(all_rows=[]),
            _FakeResult(all_rows=[]),
            _FakeResult(all_rows=[]),
        ]
    )
    result = run_retention.preview_old_runs(fake_session, days=7, batch_size=10)

    delta = datetime.now(timezone.utc) - result["cutoff"]
    assert 6.5 * 86400 <= delta.total_seconds() <= 7.5 * 86400
