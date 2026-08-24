"""P1.4 项目维度保留天数：resolve_project_retention / list_projects_with_retention_override 单测。"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules.setdefault(
    "app.core.minio_client",
    types.SimpleNamespace(
        delete_file=lambda *_a, **_kw: None,
        list_objects=lambda *_a, **_kw: [],
        read_bytes=lambda *_a, **_kw: b"",
        upload_bytes=lambda *_a, **_kw: None,
        ensure_bucket=lambda: None,
    ),
)

from app.models.bootstrap import load_all_models

load_all_models()

from app.services import run_retention


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _StubSession:
    """根据 stmt 的 selected_columns 数量区分：单列→scalar；多列→rows。"""

    def __init__(self, override_value=None, override_rows=None):
        self.override_value = override_value
        self.override_rows = override_rows or []

    def execute(self, stmt):
        try:
            col_count = len(list(stmt.selected_columns))
        except Exception:
            col_count = 0
        if col_count <= 1:
            return _ScalarResult(self.override_value)
        return _RowsResult(self.override_rows)


def test_resolve_project_retention_uses_override_when_present():
    session = _StubSession(override_value=14)
    days = run_retention.resolve_project_retention(session, project_id=5, global_days=90)
    assert days == 14


def test_resolve_project_retention_falls_back_to_global_when_none():
    session = _StubSession(override_value=None)
    days = run_retention.resolve_project_retention(session, project_id=5, global_days=90)
    assert days == 90


def test_resolve_project_retention_ignores_non_positive_override():
    """override <= 0 视为无效，沿用全局（防止意外的 0/负值清空全部数据）"""
    session = _StubSession(override_value=0)
    days = run_retention.resolve_project_retention(session, project_id=5, global_days=30)
    assert days == 30

    session = _StubSession(override_value=-1)
    days = run_retention.resolve_project_retention(session, project_id=5, global_days=30)
    assert days == 30


def test_list_projects_with_retention_override_filters_valid_only():
    rows = [
        (1, "alpha", 14),
        (2, "beta", 30),
        (3, "ignored-zero", 0),  # 应被过滤
        (4, "ignored-null", None),  # 应被过滤
    ]
    session = _StubSession(override_rows=rows)
    result = run_retention.list_projects_with_retention_override(session)
    assert result == [(1, "alpha", 14), (2, "beta", 30)]


def test_preview_old_runs_by_project_returns_global_and_projects(monkeypatch):
    """preview_old_runs_by_project 应同时返回 global + 每个 override 项目的预览。"""
    # 直接 monkeypatch 内部函数为可控行为
    calls = {"global": 0, "project_queries": []}

    def fake_preview_old_runs(_session, days, batch_size=500, **kwargs):
        calls["global"] += 1
        calls["global_kwargs"] = kwargs
        return {
            "cutoff": "x",
            "retention_days": days,
            "plan_runs": 100,
            "suite_runs": 50,
            "test_runs": 1000,
            "mobile_runs": 20,
            "estimated_objects": 5,
            "estimated_objects_sampled": False,
        }

    def fake_list_overrides(_session):
        return [(1, "alpha", 14), (2, "beta", 7)]

    class _ProjectScopedSession:
        def execute(self, stmt):
            # 简化：所有按项目计数查询都返回固定值
            calls["project_queries"].append(str(stmt)[:60])

            class _R:
                def scalar(self):
                    return 3

                def all(self):
                    return []

            return _R()

    monkeypatch.setattr(run_retention, "preview_old_runs", fake_preview_old_runs)
    monkeypatch.setattr(run_retention, "list_projects_with_retention_override", fake_list_overrides)

    result = run_retention.preview_old_runs_by_project(_ProjectScopedSession(), global_days=90)

    assert result["global"]["retention_days"] == 90
    assert result["global"]["plan_runs"] == 100
    assert len(result["projects"]) == 2
    alpha = result["projects"][0]
    assert alpha["project_id"] == 1
    assert alpha["project_name"] == "alpha"
    assert alpha["retention_days"] == 14
    assert alpha["plan_runs"] == 3
    assert alpha["suite_runs"] == 3
    assert (
        alpha["test_runs"] == 3 and alpha["mobile_runs"] == 3 and alpha["performance_runs"] == 3
    )  # 不再是全局兜底 note
    assert alpha["estimated_objects"] == 0
    assert alpha["estimated_objects_sampled"] is False
    assert "note" not in alpha
    assert calls["global_kwargs"] == {"exclude_project_ids": [1, 2]}
    # 每项目五次 count + 三次 sample id 查询（含 PerformanceRun 和压测报告样本）
    assert len(calls["project_queries"]) == 16
