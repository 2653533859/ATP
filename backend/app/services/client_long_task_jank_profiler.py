"""前端运行时长任务 (Long Task) 与主线程掉帧卡顿诊断器 (T4.1)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskAttributionType(str, Enum):
    """长任务卡顿归因分类。"""

    SCRIPT_EXECUTION = "SCRIPT_EXECUTION"  # JS 同步密集计算或大循环
    LAYOUT_THRASHING = "LAYOUT_THRASHING"  # 强制同步布局 (读写 DOM 属性交替)
    DOM_REFLOW = "DOM_REFLOW"  # 大规模 DOM 节点树重排/重绘
    GARBAGE_COLLECTION = "GARBAGE_COLLECTION"  # V8 引擎主线程停顿 GC (Stop-the-World)
    JSON_PARSING = "JSON_PARSING"  # 超大体积 JSON 反序列化阻塞
    CANVAS_RENDER = "CANVAS_RENDER"  # ECharts/Canvas 复杂图表渲染


class TbtRating(str, Enum):
    """总阻塞时间 (TBT) 健康度评级 (符合 Google Web Vitals 官方标准)。"""

    GOOD = "GOOD"  # TBT <= 200ms
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"  # 200ms < TBT <= 600ms
    POOR = "POOR"  # TBT > 600ms


@dataclass
class LongTaskItem:
    """单个长任务事件明细。"""

    task_id: str
    duration_ms: float
    blocking_duration_ms: float  # 超出 50ms 阈值的部分 (累计入 TBT)
    attribution_type: TaskAttributionType
    culprit_symbol: str
    call_stack: list[str]
    severity: str  # CRITICAL (>300ms), HIGH (>150ms), MEDIUM (>50ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "duration_ms": round(self.duration_ms, 1),
            "blocking_duration_ms": round(self.blocking_duration_ms, 1),
            "attribution_type": self.attribution_type.value,
            "culprit_symbol": self.culprit_symbol,
            "call_stack": self.call_stack,
            "severity": self.severity,
        }


@dataclass
class JankIncident:
    """掉帧卡顿事件 (单帧耗时超出 16.67ms 预算)。"""

    incident_id: str
    frame_duration_ms: float
    dropped_frames_count: int
    culprit_task_id: str
    impact_level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "frame_duration_ms": round(self.frame_duration_ms, 1),
            "dropped_frames_count": self.dropped_frames_count,
            "culprit_task_id": self.culprit_task_id,
            "impact_level": self.impact_level,
        }


@dataclass
class LongTaskJankProfileReport:
    """长任务与主线程掉帧全景诊断报告。"""

    report_id: str
    page_name: str
    total_tasks_count: int
    long_tasks_count: int
    total_duration_ms: float
    total_blocking_time_ms: float  # TBT
    tbt_rating: TbtRating
    estimated_fps: float  # 有效帧率 (0~60 FPS)
    jank_rate_pct: float  # 掉帧率 (0~100%)
    long_tasks: list[LongTaskItem]
    jank_incidents: list[JankIncident]
    remediation_recommendations: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "page_name": self.page_name,
            "total_tasks_count": self.total_tasks_count,
            "long_tasks_count": self.long_tasks_count,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "total_blocking_time_ms": round(self.total_blocking_time_ms, 1),
            "tbt_rating": self.tbt_rating.value,
            "estimated_fps": round(self.estimated_fps, 1),
            "jank_rate_pct": round(self.jank_rate_pct, 1),
            "long_tasks": [t.to_dict() for t in self.long_tasks],
            "jank_incidents": [j.to_dict() for j in self.jank_incidents],
            "remediation_recommendations": self.remediation_recommendations,
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_LONG_TASK_REPORTS: dict[str, LongTaskJankProfileReport] = {}


def clear_long_task_store() -> None:
    """清空长任务报告仓库 (单测专用)。"""
    _LONG_TASK_REPORTS.clear()


def _infer_attribution_type(culprit: str, stack: list[str]) -> TaskAttributionType:
    """依据调用栈信息推断长任务的底层归因类型。"""
    combined = (culprit + " " + " ".join(stack)).lower()
    if any(k in combined for k in ("offsettop", "clientheight", "scrolltop", "getboundingclientrect", "layout")):
        return TaskAttributionType.LAYOUT_THRASHING
    if any(k in combined for k in ("echarts", "canvas", "webgl", "renderchart")):
        return TaskAttributionType.CANVAS_RENDER
    if any(k in combined for k in ("json.parse", "json.stringify", "parsejson")):
        return TaskAttributionType.JSON_PARSING
    if any(k in combined for k in ("gc", "garbage", "major-mc", "scavenge")):
        return TaskAttributionType.GARBAGE_COLLECTION
    if any(k in combined for k in ("innerhtml", "appendchild", "reflow", "dom")):
        return TaskAttributionType.DOM_REFLOW
    return TaskAttributionType.SCRIPT_EXECUTION


def diagnose_long_tasks_and_jank(
    page_name: str,
    task_events: list[dict[str, Any]],
    sampling_duration_ms: float = 5000.0,
) -> LongTaskJankProfileReport:
    """全息分析客户端性能采样批次，量化 TBT、长任务、掉帧事件与优化指引。"""
    long_task_items: list[LongTaskItem] = []
    jank_incidents: list[JankIncident] = []
    total_blocking_time = 0.0
    total_duration = 0.0
    total_dropped_frames = 0

    for idx, t in enumerate(task_events):
        dur = float(t.get("duration_ms", 0.0))
        total_duration += dur
        culprit = str(t.get("culprit_symbol") or f"task_{idx}")
        stack = list(t.get("call_stack") or [])

        # 检查是否满足 W3C Long Task 定义 (连续占用 CPU > 50ms)
        if dur > 50.0:
            blocking_dur = dur - 50.0
            total_blocking_time += blocking_dur

            # 严重度划分
            if dur >= 300.0:
                sev = "CRITICAL"
            elif dur >= 150.0:
                sev = "HIGH"
            else:
                sev = "MEDIUM"

            attr_type = _infer_attribution_type(culprit, stack)
            task_id = f"lt_{uuid.uuid4().hex[:6]}"
            long_task_items.append(
                LongTaskItem(
                    task_id=task_id,
                    duration_ms=dur,
                    blocking_duration_ms=blocking_dur,
                    attribution_type=attr_type,
                    culprit_symbol=culprit,
                    call_stack=stack,
                    severity=sev,
                )
            )

            # 掉帧量化: 帧预算为 16.67ms
            dropped = max(1, int(dur // 16.67))
            total_dropped_frames += dropped
            impact = "FREEZE" if dur >= 300.0 else ("JANK" if dur >= 100.0 else "MICRO_STUTTER")

            jank_incidents.append(
                JankIncident(
                    incident_id=f"jank_{uuid.uuid4().hex[:6]}",
                    frame_duration_ms=dur,
                    dropped_frames_count=dropped,
                    culprit_task_id=task_id,
                    impact_level=impact,
                )
            )

    # 计算 TBT 评级
    if total_blocking_time <= 200.0:
        tbt_rating = TbtRating.GOOD
    elif total_blocking_time <= 600.0:
        tbt_rating = TbtRating.NEEDS_IMPROVEMENT
    else:
        tbt_rating = TbtRating.POOR

    # 计算有效帧率与掉帧率
    # 周期内总期望帧数 = sampling_duration_ms / 16.67
    expected_frames = max(1.0, sampling_duration_ms / 16.67)
    actual_frames = max(0.0, expected_frames - total_dropped_frames)
    estimated_fps = min(60.0, (actual_frames / expected_frames) * 60.0)
    jank_rate = min(100.0, (total_dropped_frames / expected_frames) * 100.0)

    # 针对性调优指引生成
    recommendations: list[str] = []
    attr_types_present = {t.attribution_type for t in long_task_items}

    if TaskAttributionType.LAYOUT_THRASHING in attr_types_present:
        recommendations.append(
            "存在强制同步布局 (Layout Thrashing)，避免在同一个循环中读写 offsetTop/clientHeight 等几何属性，批量集中读取与写入。"
        )
    if TaskAttributionType.CANVAS_RENDER in attr_types_present:
        recommendations.append(
            "ECharts/Canvas 渲染耗时过长，建议开启 progressive 渐进式渲染或通过 requestAnimationFrame 进行图表重绘节流。"
        )
    if TaskAttributionType.JSON_PARSING in attr_types_present:
        recommendations.append(
            "超大 JSON 数据反序列化阻塞主线程，建议拆包轻量化字段或在 Web Worker 中执行 JSON.parse()。"
        )
    if TaskAttributionType.SCRIPT_EXECUTION in attr_types_present:
        recommendations.append(
            "主线程同步运算过载，建议使用 scheduler.yield() 或 requestIdleCallback() 将长任务切片打散，保障输入及时响应。"
        )
    if total_blocking_time > 600.0:
        recommendations.append(
            f"当前 TBT 累计高达 {total_blocking_time:.1f}ms (评级 POOR)，严重影响 Google Web Vitals FID/INP 指标，需优先治理。"
        )

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", page_name)[:16]
    report_id = f"lt_prof_{safe_name}_{int(now.timestamp())}"

    report = LongTaskJankProfileReport(
        report_id=report_id,
        page_name=page_name,
        total_tasks_count=len(task_events),
        long_tasks_count=len(long_task_items),
        total_duration_ms=total_duration,
        total_blocking_time_ms=total_blocking_time,
        tbt_rating=tbt_rating,
        estimated_fps=estimated_fps,
        jank_rate_pct=jank_rate,
        long_tasks=long_task_items,
        jank_incidents=jank_incidents,
        remediation_recommendations=recommendations,
        created_at=now,
    )

    _LONG_TASK_REPORTS[report_id] = report
    return report


def get_long_task_report(report_id: str) -> LongTaskJankProfileReport | None:
    """按 ID 查询长任务诊断报告。"""
    return _LONG_TASK_REPORTS.get(report_id)


def list_long_task_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史长任务报告列表。"""
    reports = list(reversed(list(_LONG_TASK_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
