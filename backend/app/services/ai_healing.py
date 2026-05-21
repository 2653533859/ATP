"""P3.A AI 用例自愈：失败 step 的异步诊断服务。

核心契约：
- `apply_healing_hook(step_result)` 在 executor commit 前调用（同步函数）。
  根据 step 状态与全局开关 / 项目 ai_llm_config 决定 healing_status：
    - step 非 failed/error → 不动，返回 False
    - AI_HEALING_ENABLED=False → 标 skipped，返回 False
    - 否则标 pending，返回 True；调用方在 commit 后 enqueue Celery 任务
- `enqueue_diagnosis(step_result_id)` 提交 Celery 任务到队列。
- `run_diagnosis(step_result_id)` 真正的诊断主体：拉 step+run+case+project+ai_llm_config，
  构造 prompt → 调 LLM → 写回 healing_suggestion/status/at → publish ws 事件。

设计原则：
- 失败 step 的诊断必须 **异步**，不阻塞 executor 与 run 状态推进
- 项目未配置 ai_llm_config 或 LLM 调用异常：写 status=failed + 简短 fallback message
- 不送截图（多模态留后续迭代），仅 error_message + request/response 文本
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.case import RunStatus, StepResult, TestCase, TestRun

logger = logging.getLogger(__name__)


# ── 同步 hook：executor 调用 ───────────────────────────────────
def apply_healing_hook(step_result: StepResult) -> bool:
    """判定 step 是否需要异步诊断，并就地修改 healing_status。

    返回 True 表示调用方应该在 commit 后调 `enqueue_diagnosis(step_result.id)`。
    """
    if step_result.status not in (RunStatus.failed, RunStatus.error):
        return False
    if not settings.AI_HEALING_ENABLED:
        step_result.healing_status = "skipped"
        return False
    step_result.healing_status = "pending"
    return True


def enqueue_diagnosis(step_result_id: int) -> None:
    """入队失败的兜底：执行不中断；下次手动触发即可（本期不实现重试）。"""
    try:
        from app.worker.tasks_healing import diagnose_step_failure

        diagnose_step_failure.delay(step_result_id)
    except Exception:
        logger.exception("enqueue diagnose_step_failure failed for step_result_id=%s", step_result_id)


# ── prompt 构造 ────────────────────────────────────────────────
_MAX_FIELD_CHARS = 2000


def _truncate(value, limit: int = _MAX_FIELD_CHARS) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    else:
        text = str(value)
    return text if len(text) <= limit else text[:limit] + " …(truncated)"


def build_healing_prompt(
    *,
    case_type: str,
    case_name: str,
    step_name: str,
    error_message: str | None,
    request_data,
    response_data,
    run_summary: dict | None = None,
) -> str:
    """按 case_type 分文案构造 prompt。"""
    parts = [
        f"# 用例类型: {case_type}",
        f"# 用例名称: {case_name}",
        f"# 失败步骤: {step_name}",
    ]
    if error_message:
        parts.append(f"# 错误信息:\n{_truncate(error_message)}")
    if request_data:
        parts.append(f"# 请求数据:\n{_truncate(request_data)}")
    if response_data:
        parts.append(f"# 响应数据:\n{_truncate(response_data)}")
    if run_summary:
        parts.append(f"# 运行摘要:\n{_truncate(run_summary, limit=500)}")
    parts.append(
        "\n请基于以上失败上下文，给出："
        "\n1) 最可能的根因（一句话）"
        "\n2) 修复建议（具体到字段 / 断言 / 配置项 / 步骤顺序，避免泛泛"
        "而谈）"
        "\n3) 若环境问题，给出排查路径"
        "\n用中文回答，控制在 200 字以内。"
    )
    return "\n\n".join(parts)


# ── 主诊断流程（异步）─────────────────────────────────────────
async def run_diagnosis(db: AsyncSession, step_result_id: int) -> None:
    """诊断单个失败 step。Celery task 体调用此函数。

    幂等：若 healing_status 已为 done/failed/skipped，跳过；只处理 pending（或 NULL 兜底）。
    """
    from app.core.encryption import decrypt
    from app.core.redis_client import publish_run_event
    from app.models.ai_llm_config import AILLMConfig
    from app.models.project import Project
    from app.services.ai_case.llm_client import LLMRequest, call_llm

    step = await db.get(StepResult, step_result_id)
    if step is None:
        logger.warning("run_diagnosis: step_result_id=%s not found", step_result_id)
        return

    if step.healing_status in ("done", "failed", "skipped"):
        return  # 幂等

    # 拉关联：run → case → module → project（避免动 ORM 关系也能跑）
    run = await db.get(TestRun, step.run_id)
    if run is None:
        await _finalize(db, step, status="failed", message="run 已删除")
        return

    case = await db.get(TestCase, run.case_id)
    if case is None:
        await _finalize(db, step, status="failed", message="case 已删除")
        return

    # case.module_id → module.project_id
    from app.models.project import Module

    module = await db.get(Module, case.module_id)
    project = await db.get(Project, module.project_id) if module else None

    if project is None or project.ai_llm_config_id is None:
        await _finalize(db, step, status="skipped", message=None)
        await _safe_publish(run.id, step, "skipped", None)
        return

    config = await db.get(AILLMConfig, project.ai_llm_config_id)
    if config is None or not config.enabled:
        await _finalize(db, step, status="skipped", message=None)
        await _safe_publish(run.id, step, "skipped", None)
        return

    # 构造 prompt + 调 LLM
    try:
        api_key = decrypt(config.api_key_encrypted)
    except Exception:
        await _finalize(db, step, status="failed", message="LLM API key 解密失败")
        await _safe_publish(run.id, step, "failed", "LLM API key 解密失败")
        return

    prompt = build_healing_prompt(
        case_type=case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type),
        case_name=case.name,
        step_name=step.name,
        error_message=step.error_message,
        request_data=step.request_data,
        response_data=step.response_data,
        run_summary=run.result_summary,
    )

    try:
        response = await call_llm(
            LLMRequest(
                provider=config.provider,
                api_key=api_key,
                model_name=config.model_name,
                prompt=prompt,
                endpoint=config.endpoint,
                timeout_seconds=float(settings.AI_HEALING_TIMEOUT_SECONDS),
                extra_params=config.default_params,
            )
        )
    except Exception as exc:
        logger.warning("AI healing LLM call failed: %s", exc)
        await _finalize(db, step, status="failed", message=f"LLM 调用失败: {exc}")
        await _safe_publish(run.id, step, "failed", str(exc))
        return

    text = (response.text or "").strip() or "（LLM 未返回内容）"
    await _finalize(db, step, status="done", message=text)
    await _safe_publish(run.id, step, "done", text)


async def _finalize(db: AsyncSession, step: StepResult, *, status: str, message: str | None) -> None:
    step.healing_status = status
    step.healing_suggestion = message
    step.healing_at = datetime.now(timezone.utc)
    await db.commit()


async def _safe_publish(run_id: int, step: StepResult, status: str, suggestion: str | None) -> None:
    from app.core.redis_client import publish_run_event

    try:
        await publish_run_event(
            run_id,
            {
                "type": "healing_suggestion",
                "run_id": run_id,
                "step_id": step.id,
                "step_index": step.step_index,
                "status": status,
                "suggestion": suggestion,
            },
        )
    except Exception:
        return  # best-effort
