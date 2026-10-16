"""前端运行时长任务与掉帧卡顿诊断器单元测试 (T4.1)。"""

from __future__ import annotations

import pytest
from app.services.client_long_task_jank_profiler import (
    TaskAttributionType,
    TbtRating,
    clear_long_task_store,
    diagnose_long_tasks_and_jank,
    get_long_task_report,
    list_long_task_reports,
)


@pytest.fixture(autouse=True)
def _reset_long_task_state():
    clear_long_task_store()
    yield
    clear_long_task_store()


def test_diagnose_long_tasks_and_jank_heavy_load():
    """测试探测多个长任务、计算 TBT (POOR)、掉帧事件与归因推荐。"""
    events = [
        # 1. 强制同步布局 (Layout Thrashing) - 耗时 250ms -> blocking = 200ms
        {
            "duration_ms": 250.0,
            "culprit_symbol": "calculateTableLayout",
            "call_stack": ["read offsetTop", "write style.height", "updateDOM"],
        },
        # 2. 超长 JS 运算 (Freeze) - 耗时 550ms -> blocking = 500ms
        {
            "duration_ms": 550.0,
            "culprit_symbol": "processLargeDataBatch",
            "call_stack": ["matrixMultiplication", "heavyLoop"],
        },
        # 3. 正常微小任务 (< 50ms) - 耗时 12ms -> 不计入长任务与 TBT
        {
            "duration_ms": 12.0,
            "culprit_symbol": "handleClick",
            "call_stack": ["emitEvent"],
        },
    ]

    report = diagnose_long_tasks_and_jank(
        page_name="dashboard_heavy_view",
        task_events=events,
        sampling_duration_ms=5000.0,
    )

    assert report.total_tasks_count == 3
    assert report.long_tasks_count == 2
    # TBT = (250-50) + (550-50) = 200 + 500 = 700ms > 600ms -> POOR
    assert report.total_blocking_time_ms == 700.0
    assert report.tbt_rating == TbtRating.POOR
    assert len(report.jank_incidents) == 2

    # 验证归因
    attr_types = {t.attribution_type for t in report.long_tasks}
    assert TaskAttributionType.LAYOUT_THRASHING in attr_types
    assert TaskAttributionType.SCRIPT_EXECUTION in attr_types

    # 验证优化指引输出
    assert len(report.remediation_recommendations) >= 2


def test_diagnose_long_tasks_smooth_performance():
    """测试无长任务、丝滑 60 FPS 体验。"""
    events = [
        {"duration_ms": 8.0, "culprit_symbol": "tick1"},
        {"duration_ms": 14.0, "culprit_symbol": "tick2"},
        {"duration_ms": 16.0, "culprit_symbol": "tick3"},
    ]

    report = diagnose_long_tasks_and_jank(
        page_name="smooth_page",
        task_events=events,
        sampling_duration_ms=5000.0,
    )

    assert report.long_tasks_count == 0
    assert report.total_blocking_time_ms == 0.0
    assert report.tbt_rating == TbtRating.GOOD
    assert report.estimated_fps == 60.0
    assert report.jank_rate_pct == 0.0

    saved = get_long_task_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_long_task_reports()) == 1
