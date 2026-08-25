"""Rule-based failure diagnosis for non-case workbench tasks.

Case runs already have the richer ``failure_diagnosis`` service.  This module
keeps the workbench fallback small and domain-aware for suite, plan, Android,
and performance runs without sending execution configuration to an LLM.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypeVar, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mobile_special import MobileIncident, MobileRunEvent, MobileSpecialRun, MobileSpecialTask
from app.models.performance import PerformanceRun, PerformanceTest
from app.models.plan import PlanRun, TestPlan
from app.models.suite import SuiteRun, TestSuite

_MAX_TEXT = 320
_FAILED_STATUSES = {"failed", "error", "cancelled", "stopped"}
ModelT = TypeVar("ModelT")


async def _db_get(db: AsyncSession, model: type[ModelT], object_id: int) -> ModelT | None:
    """Keep SQLAlchemy's overloaded ``get`` type independent per model."""

    return cast(ModelT | None, await db.get(cast(Any, model), object_id))


def _truncate(value: Any, limit: int = _MAX_TEXT) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = str(value)
    else:
        text = str(value)
    text = " ".join(text.replace("\x00", " ").split())
    return text if len(text) <= limit else text[:limit] + " ...(truncated)"


def _number(summary: dict[str, Any], key: str) -> float | None:
    value = summary.get(key)
    if isinstance(value, bool):
        return None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _suggestion(*, name: str, target: str, change: str, evidence: str, kind: str = "investigate_environment") -> dict:
    return {
        "step_index": 0,
        "step_name": name,
        "suggestion_type": kind,
        "target": target,
        "suggested_change": change,
        "evidence": evidence or "未记录结构化错误信息",
        "confidence": 0.72,
    }


def build_rule_task_diagnosis(
    *,
    task_type: str,
    run_id: int,
    status: str,
    task_name: str | None = None,
    error_message: str | None = None,
    summary: dict[str, Any] | None = None,
    incident_count: int = 0,
    event_error_count: int = 0,
) -> dict[str, Any]:
    """Build a bounded, domain-specific diagnosis from persisted run facts."""

    data = summary if isinstance(summary, dict) else {}
    error = _truncate(error_message or data.get("error_message"))
    evidence: list[str] = []
    suggestions: list[dict] = []
    title = task_name or f"{task_type} 执行摘要"

    if task_type == "android":
        crash_count = int(_number(data, "crash_count") or 0)
        anr_count = int(_number(data, "anr_count") or 0)
        jank_count = int(_number(data, "total_jank_count") or 0)
        if crash_count:
            category = "应用崩溃或运行时异常"
            evidence.extend([f"crash_count={crash_count}", f"incident_count={incident_count}"])
            change = "先查看崩溃/异常 artifact 与设备日志，确认进程、堆栈和触发动作，再复现相同配置。"
            target = "device_logs_and_artifacts"
        elif anr_count:
            category = "应用无响应（ANR）"
            evidence.append(f"anr_count={anr_count}")
            change = "检查 ANR trace、主线程阻塞和设备负载，确认是应用耗时操作还是设备资源不足。"
            target = "anr_trace_and_device_load"
        elif jank_count:
            category = "界面卡顿或帧耗时异常"
            evidence.append(f"jank_count={jank_count}")
            change = "结合帧率采样、操作时间线和 Perfetto/录制证据定位卡顿动作，再调整应用或设备前置条件。"
            target = "fluency_samples_and_timeline"
        elif error:
            category = "Android 设备、应用或前置操作异常"
            target = "device_preflight"
            change = "核对设备连接、应用包名、权限和前置操作日志，确认失败发生在设备准备还是业务动作阶段。"
        else:
            category = "Android 执行未完成"
            target = "android_run_events"
            change = "查看执行事件时间线和最后一个错误级事件，补充设备日志后再复跑。"
        if event_error_count:
            evidence.append(f"event_error_count={event_error_count}")
        if jank_count and task_type == "android":
            evidence.append(f"jank_count={jank_count}")
        suggestions.append(_suggestion(name=title, target=target, change=change, evidence="；".join(evidence)))
    elif task_type == "performance":
        error_rate = _number(data, "error_rate")
        p95_ms = _number(data, "p95_ms")
        if error:
            category = "压测执行器、节点或依赖服务异常"
            target = "executor_and_node"
            change = "先核对压测节点、执行器日志、目标服务连通性和资源水位，确认是否在业务指标分析前已失败。"
        elif error_rate is not None and error_rate > 0:
            category = "请求错误率异常"
            target = "error_rate_and_response"
            change = "按状态码和接口分组检查错误响应、环境变量及认证配置，避免只提高阈值掩盖真实失败。"
        elif p95_ms is not None:
            category = "响应延迟或性能阈值异常"
            target = "latency_threshold_and_baseline"
            change = "对照性能基线检查 p95/p99、并发模型和节点资源，确认是回归还是负载模型变化。"
        else:
            category = "压测结果缺少可判定指标"
            target = "performance_summary"
            change = "确认执行器是否上传完整结果摘要，并检查压测节点和原始结果对象。"
        if error_rate is not None:
            evidence.append(f"error_rate={error_rate:g}")
        if p95_ms is not None:
            evidence.append(f"p95_ms={p95_ms:g}")
        suggestions.append(_suggestion(name=title, target=target, change=change, evidence="；".join(evidence)))
    else:
        counts = ", ".join(f"{key}={data[key]}" for key in ("total", "failed", "error") if key in data)
        category = "套件或计划中的子任务失败"
        target = "child_runs_and_dependencies"
        change = "打开套件/计划关联的子执行记录，定位首个失败用例和共享前置条件，再单独复跑确认。"
        evidence.extend([item for item in (counts, error) if item])
        suggestions.append(_suggestion(name=title, target=target, change=change, evidence="；".join(evidence)))

    if error:
        evidence.append(f"error={error}")
    if status not in _FAILED_STATUSES:
        return {
            "status": "skipped",
            "source": "rule",
            "summary": "当前执行未标记为失败或异常，暂无需要诊断的失败原因。",
            "at": datetime.now(timezone.utc).isoformat(),
            "failed_step_count": 0,
            "screenshot_count": int(_number(data, "screenshot_count") or 0),
            "repair_suggestions": [],
            "error_samples": [],
        }

    summary_text = f"最可能原因：{category}。"
    if evidence:
        summary_text += f" 关键证据：{'；'.join(evidence[:4])}。"
    summary_text += " 建议按下方证据链排查，修复后复跑确认。"

    return {
        "status": "done",
        "source": "rule",
        "summary": summary_text,
        "at": datetime.now(timezone.utc).isoformat(),
        "failed_step_count": 1,
        "screenshot_count": int(_number(data, "screenshot_count") or 0),
        "repair_suggestions": suggestions,
        "error_samples": [{"step_index": 0, "name": title, "error_message": error}] if error else [],
    }


async def generate_workbench_failure_diagnosis(
    db: AsyncSession,
    task_type: str,
    run_id: int,
) -> dict[str, Any] | None:
    """Load one non-case run and produce a rule diagnosis from its own evidence."""

    if task_type == "case":
        from app.services.failure_diagnosis import generate_failure_diagnosis

        return await generate_failure_diagnosis(db, run_id)

    if task_type == "suite":
        suite_run = await _db_get(db, SuiteRun, run_id)
        if suite_run is None:
            return None
        suite = await _db_get(db, TestSuite, suite_run.suite_id)
        return build_rule_task_diagnosis(
            task_type=task_type,
            run_id=suite_run.id,
            status=getattr(suite_run.status, "value", suite_run.status),
            task_name=suite.name if suite else None,
            error_message=suite_run.error_message,
            summary=suite_run.result_summary,
        )

    if task_type == "plan":
        plan_run = await _db_get(db, PlanRun, run_id)
        if plan_run is None:
            return None
        plan = await _db_get(db, TestPlan, plan_run.plan_id)
        return build_rule_task_diagnosis(
            task_type=task_type,
            run_id=plan_run.id,
            status=getattr(plan_run.status, "value", plan_run.status),
            task_name=plan.name if plan else None,
            error_message=plan_run.error_message,
            summary=plan_run.result_summary,
        )

    if task_type == "android":
        android_run = await _db_get(db, MobileSpecialRun, run_id)
        if android_run is None:
            return None
        task = await _db_get(db, MobileSpecialTask, android_run.task_id)
        incident_result = await db.execute(
            select(func.count()).select_from(MobileIncident).where(MobileIncident.run_id == android_run.id)
        )
        event_result = await db.execute(
            select(func.count())
            .select_from(MobileRunEvent)
            .where(MobileRunEvent.run_id == android_run.id, MobileRunEvent.level == "error")
        )
        return build_rule_task_diagnosis(
            task_type=task_type,
            run_id=android_run.id,
            status=getattr(android_run.status, "value", android_run.status),
            task_name=task.name if task else None,
            error_message=(android_run.summary_json or {}).get("error_message")
            if isinstance(android_run.summary_json, dict)
            else None,
            summary=android_run.summary_json,
            incident_count=int(incident_result.scalar_one() or 0),
            event_error_count=int(event_result.scalar_one() or 0),
        )

    if task_type == "performance":
        performance_run = await _db_get(db, PerformanceRun, run_id)
        if performance_run is None:
            return None
        performance_test = await _db_get(db, PerformanceTest, performance_run.performance_test_id)
        return build_rule_task_diagnosis(
            task_type=task_type,
            run_id=performance_run.id,
            status=str(performance_run.status),
            task_name=performance_test.name if performance_test else None,
            error_message=performance_run.error_message,
            summary=performance_run.summary,
        )

    return None
