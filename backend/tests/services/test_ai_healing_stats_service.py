"""`services/ai_healing_stats.py` 的行为缝（Q15-05）。

该模块此前 26% 覆盖 —— 只有模块导入和两个小 helper 被执行过，
`build_ai_healing_stats` 的 8 次查询、指纹分桶、Top10 截断与生产回归统计一行没跑。
它是 AI 自愈统计页的唯一数据来源，聚合口径出错不会报错，只会把数字算错。

按仓库既有约定用脚本化 FakeDB：`db.execute` 按调用顺序返回预置结果，
不连真库也不 mock SQLAlchemy 语句构造（语句仍然真实构建一遍）。
"""

from __future__ import annotations

import types
from datetime import date, datetime, timezone

import pytest

from app.services.ai_healing_stats import _rate, build_ai_healing_stats


class _Result:
    """覆盖 build_ai_healing_stats 用到的全部结果读取方式。"""

    def __init__(self, rows=None, scalar=None, scalars=None):
        self._rows = rows or []
        self._scalar = scalar
        self._scalars = scalars or []

    def one(self):
        return self._rows[0]

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return types.SimpleNamespace(all=lambda: self._scalars)


class _FakeDB:
    def __init__(self, results: list[_Result]):
        self._results = list(results)
        self.executed = 0

    async def execute(self, _statement):
        self.executed += 1
        if not self._results:
            raise AssertionError("db.execute 次数超过预置结果数")
        return self._results.pop(0)


def _step(name, feedback, *, error="boom", status_code=500):
    return types.SimpleNamespace(
        name=name,
        healing_feedback=feedback,
        error_message=error,
        response_data={"status_code": status_code},
    )


def _empty_results() -> list[_Result]:
    return [
        _Result(rows=[(0, 0, 0)]),  # 总计
        _Result(rows=[]),  # 按用例类型
        _Result(rows=[]),  # 指纹明细
        _Result(rows=[]),  # 趋势
        _Result(scalar=0),  # 高质量样例
        _Result(scalars=[]),  # 生产回归
        _Result(scalar=None),  # 最近聚合时间
    ]


def test_rate_is_zero_when_there_is_no_denominator():
    assert _rate(0, 0) == 0.0
    assert _rate(3, 4) == 75.0
    assert _rate(1, 3) == 33.33


@pytest.mark.asyncio
async def test_empty_window_reports_zeros_without_dividing_by_zero():
    db = _FakeDB(_empty_results())

    stats = await build_ai_healing_stats(db, days=7)

    assert db.executed == 7
    assert stats.total_feedback_count == 0
    assert stats.adopted_rate == 0.0
    assert stats.by_case_type == []
    assert stats.top_error_fingerprints == []
    assert stats.recent_trend == []
    assert stats.high_quality_example_count == 0
    assert stats.production_feedback.regression_triggered_count == 0
    assert stats.production_feedback.regression_success_rate == 0.0
    assert stats.production_feedback.latest_feedback_aggregated_at is None


@pytest.mark.asyncio
async def test_full_window_aggregates_every_section():
    aggregated_at = datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc)
    results = [
        _Result(rows=[(10, 6, 4)]),
        _Result(rows=[("api", 8, 5, 3), ("web", 2, 1, 1)]),
        _Result(
            rows=[
                (_step("登录", "adopted"), "api"),
                (_step("登录", "adopted"), "api"),
                (_step("登录", "rejected"), "api"),
                (_step("下单", "adopted"), "web"),
            ]
        ),
        _Result(rows=[(date(2026, 7, 29), 4, 3, 1), (date(2026, 7, 30), 6, 3, 3)]),
        _Result(scalar=12),
        _Result(
            scalars=[
                types.SimpleNamespace(result_summary={"triggered_by_ai_healing_patch": True}, status="passed"),
                types.SimpleNamespace(result_summary={"triggered_by_ai_healing_patch": True}, status="failed"),
                # 非自愈触发的运行不计入分母
                types.SimpleNamespace(result_summary={"other": 1}, status="passed"),
                types.SimpleNamespace(result_summary="not-a-dict", status="passed"),
            ]
        ),
        _Result(scalar=aggregated_at),
    ]

    stats = await build_ai_healing_stats(_FakeDB(results))

    assert stats.total_feedback_count == 10
    assert stats.adopted_count == 6 and stats.rejected_count == 4
    assert stats.adopted_rate == 60.0

    assert [item.case_type for item in stats.by_case_type] == ["api", "web"]
    assert stats.by_case_type[0].adopted_rate == 62.5

    # 同一 (指纹, 用例类型) 合并计数，不同步骤名分开
    api_bucket = next(item for item in stats.top_error_fingerprints if item.case_type == "api")
    assert api_bucket.total_count == 3
    assert api_bucket.adopted_count == 2 and api_bucket.rejected_count == 1
    # 按 total_count 降序：api 的 3 条排在 web 的 1 条之前
    assert stats.top_error_fingerprints[0].case_type == "api"

    assert [item.date for item in stats.recent_trend] == ["2026-07-29", "2026-07-30"]
    assert stats.recent_trend[0].adopted_rate == 75.0

    assert stats.high_quality_example_count == 12
    assert stats.production_feedback.regression_triggered_count == 2
    assert stats.production_feedback.regression_success_count == 1
    assert stats.production_feedback.regression_success_rate == 50.0
    assert stats.production_feedback.latest_feedback_aggregated_at == aggregated_at.isoformat()


@pytest.mark.asyncio
async def test_top_fingerprints_are_truncated_to_ten():
    steps = [(_step(f"步骤{index}", "adopted"), "api") for index in range(15)]
    results = _empty_results()
    results[2] = _Result(rows=steps)

    stats = await build_ai_healing_stats(_FakeDB(results))

    assert len(stats.top_error_fingerprints) == 10, "Top 指纹固定截断到 10 条"


@pytest.mark.asyncio
async def test_null_sums_from_the_database_are_treated_as_zero():
    """SUM(CASE …) 在没有匹配行时返回 NULL，不能直接 int(None)。"""
    results = _empty_results()
    results[0] = _Result(rows=[(None, None, None)])
    results[1] = _Result(rows=[("api", None, None, None)])
    results[3] = _Result(rows=[(date(2026, 7, 29), None, None, None)])
    results[4] = _Result(scalar=None)

    stats = await build_ai_healing_stats(_FakeDB(results))

    assert stats.total_feedback_count == 0
    assert stats.by_case_type[0].total_count == 0
    assert stats.by_case_type[0].adopted_rate == 0.0
    assert stats.recent_trend[0].total_count == 0
    assert stats.high_quality_example_count == 0


@pytest.mark.asyncio
async def test_enum_valued_case_types_and_statuses_are_unwrapped():
    """case_type / status 可能是枚举也可能是字符串，两种都要能取到值。"""
    results = _empty_results()
    results[1] = _Result(rows=[(types.SimpleNamespace(value="android"), 2, 2, 0)])
    results[5] = _Result(
        scalars=[
            types.SimpleNamespace(
                result_summary={"triggered_by_ai_healing_patch": True},
                status=types.SimpleNamespace(value="success"),
            )
        ]
    )

    stats = await build_ai_healing_stats(_FakeDB(results))

    assert stats.by_case_type[0].case_type == "android"
    assert stats.production_feedback.regression_success_count == 1
