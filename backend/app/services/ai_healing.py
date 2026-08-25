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

二迭代降本机制：
- 错误特征缓存：相同 (case_type, step_name, error_message[:500], response_status_code)
  在 AI_HEALING_CACHE_TTL_SECONDS 内复用上次诊断结果，跳过 LLM 调用
- 每日上限：AI_HEALING_DAILY_LIMIT > 0 时，超出当日实际 LLM 调用次数则 status=skipped
  + message 提示，避免成本失控（缓存命中不计入上限）

设计原则：
- 失败 step 的诊断必须 **异步**，不阻塞 executor 与 run 状态推进
- 项目未配置 ai_llm_config 或 LLM 调用异常：写 status=failed + 简短 fallback message
- 不送截图（多模态留后续迭代），仅 error_message + request/response 文本
"""

from __future__ import annotations

import hashlib
import json
import logging
import base64
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.case import RunStatus, StepResult, TestCase, TestRun

logger = logging.getLogger(__name__)


_CACHE_KEY_PREFIX = "ai_healing:cache:"
_DAILY_COUNT_PREFIX = "ai_healing:daily_count:"
_VISION_DAILY_COUNT_PREFIX = "ai_healing:vision_daily_count:"
_DAILY_COUNT_TTL_SECONDS = 60 * 60 * 36  # 36h，足够跨过单日时区差且自动回收


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
    few_shot_block: str | None = None,
) -> str:
    """按 case_type 分文案构造 prompt。"""
    parts = [
        f"# 用例类型: {case_type}",
        f"# 用例名称: {case_name}",
        f"# 失败步骤: {step_name}",
    ]
    if few_shot_block:
        parts.append(few_shot_block)
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
def _make_cache_key(case_type: str, step_name: str, error_message: str | None, response_status_code) -> str:
    """构造错误特征 hash，作为缓存键。

    粒度：case_type + step_name + error_message[:500] + response.status_code（若有）
    粒度过粗会复用错位（不同断言失败拿到相同建议），过细则几乎不命中。
    """
    parts = [
        case_type or "",
        step_name or "",
        (error_message or "")[:500],
        str(response_status_code if response_status_code is not None else ""),
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8", errors="replace")).hexdigest()
    return f"{_CACHE_KEY_PREFIX}{digest[:32]}"


async def _get_cached_suggestion(key: str) -> str | None:
    if settings.AI_HEALING_CACHE_TTL_SECONDS <= 0:
        return None
    try:
        from app.core.redis_client import get_json_cache

        data = await get_json_cache(key)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    suggestion = data.get("suggestion")
    return suggestion if isinstance(suggestion, str) and suggestion else None


async def _write_cached_suggestion(key: str, suggestion: str) -> None:
    if settings.AI_HEALING_CACHE_TTL_SECONDS <= 0:
        return
    try:
        from app.core.redis_client import set_json_cache

        await set_json_cache(key, {"suggestion": suggestion}, ttl_seconds=settings.AI_HEALING_CACHE_TTL_SECONDS)
    except Exception:
        return  # 写缓存失败不影响主流程


async def _check_and_incr_daily_limit() -> bool:
    """日上限检查：返回 True 表示允许调用 LLM；False 表示超限应跳过。

    AI_HEALING_DAILY_LIMIT=0 表示不限；Redis 不可达时降级为放行（best-effort 限流）。
    """
    limit = settings.AI_HEALING_DAILY_LIMIT
    if limit <= 0:
        return True
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"{_DAILY_COUNT_PREFIX}{today}"
    try:
        from app.core.redis_client import close_async_redis, get_async_redis

        r = get_async_redis()
        try:
            value = await r.incr(key)
            if value == 1:
                await r.expire(key, _DAILY_COUNT_TTL_SECONDS)
            return value <= limit
        finally:
            await close_async_redis(r)
    except Exception:
        return True  # Redis 故障不应阻塞诊断


async def _check_and_incr_vision_daily_limit() -> bool:
    limit = settings.AI_HEALING_VISION_DAILY_LIMIT
    if limit <= 0:
        return True
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"{_VISION_DAILY_COUNT_PREFIX}{today}"
    try:
        from app.core.redis_client import close_async_redis, get_async_redis

        r = get_async_redis()
        try:
            value = await r.incr(key)
            if value == 1:
                await r.expire(key, _DAILY_COUNT_TTL_SECONDS)
            return value <= limit
        finally:
            await close_async_redis(r)
    except Exception:
        return True


def _guess_image_media_type(object_name: str) -> str:
    lower = object_name.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/png"


async def _load_screenshot_image_for_llm(screenshot_url: str | None) -> tuple[str, str] | None:
    if not screenshot_url:
        return None
    try:
        from app.core.minio_client import read_bytes
        from app.core.object_refs import extract_object_name

        object_name = extract_object_name(screenshot_url)
        if not object_name:
            return None
        data = read_bytes(object_name)
        if not data:
            return None
        return base64.b64encode(data).decode("ascii"), _guess_image_media_type(object_name)
    except Exception as exc:
        logger.warning("AI healing screenshot load failed: %s", exc)
        return None


async def run_diagnosis(db: AsyncSession, step_result_id: int) -> None:
    """诊断单个失败 step。Celery task 体调用此函数。

    幂等：若 healing_status 已为 done/failed/skipped，跳过；只处理 pending（或 NULL 兜底）。
    """
    from app.core.encryption import decrypt
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

    # ── 缓存命中 fast path（不计入日上限）──────────────────
    case_type = case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type)
    response_status = None
    if isinstance(step.response_data, dict):
        response_status = step.response_data.get("status_code")
    cache_key = _make_cache_key(case_type, step.name, step.error_message, response_status)

    cached = await _get_cached_suggestion(cache_key)
    if cached:
        await _finalize(db, step, status="done", message=cached)
        await _safe_publish(run.id, step, "done", cached, cache_hit=True)
        return

    few_shot_block = ""
    if settings.AI_HEALING_FEW_SHOT_ENABLED:
        try:
            from app.services.healing_prompt_examples import build_few_shot_block, get_high_quality_examples

            examples = await get_high_quality_examples(
                db,
                error_fingerprint=cache_key.rsplit(":", 1)[-1],
                case_type=case_type,
                limit=settings.AI_HEALING_FEW_SHOT_TOP_N,
            )
            few_shot_block = build_few_shot_block(examples)
        except Exception as exc:
            logger.warning("AI healing few-shot lookup failed: %s", exc)

    # ── 日上限检查（实际要调 LLM 才计数）───────────────────
    if not await _check_and_incr_daily_limit():
        await _finalize(db, step, status="skipped", message="daily-limit-reached")
        await _safe_publish(run.id, step, "skipped", "daily-limit-reached")
        return

    # 构造 prompt + 调 LLM
    try:
        api_key = (
            ""
            if getattr(config, "provider", None) == "ollama" and not config.api_key_encrypted
            else decrypt(config.api_key_encrypted)
        )
    except Exception:
        await _finalize(db, step, status="failed", message="LLM API key 解密失败")
        await _safe_publish(run.id, step, "failed", "LLM API key 解密失败")
        return

    prompt = build_healing_prompt(
        case_type=case_type,
        case_name=case.name,
        step_name=step.name,
        error_message=step.error_message,
        request_data=step.request_data,
        response_data=step.response_data,
        run_summary=run.result_summary,
        few_shot_block=few_shot_block,
    )

    image_base64 = None
    image_media_type = "image/png"
    if settings.AI_HEALING_VISION_ENABLED and config.supports_vision and step.screenshot_url:
        image_payload = await _load_screenshot_image_for_llm(step.screenshot_url)
        if image_payload:
            if await _check_and_incr_vision_daily_limit():
                image_base64, image_media_type = image_payload
            else:
                logger.warning("AI healing vision daily limit reached; fallback to text-only diagnosis")

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
                image_base64=image_base64,
                image_media_type=image_media_type,
            )
        )
    except Exception as exc:
        logger.warning("AI healing LLM call failed: %s", exc)
        await _finalize(db, step, status="failed", message=f"LLM 调用失败: {exc}")
        await _safe_publish(run.id, step, "failed", str(exc))
        return

    text = (response.text or "").strip() or "（LLM 未返回内容）"
    await _finalize(db, step, status="done", message=text)
    await _write_cached_suggestion(cache_key, text)
    await _safe_publish(run.id, step, "done", text, cache_hit=False)


async def _finalize(db: AsyncSession, step: StepResult, *, status: str, message: str | None) -> None:
    step.healing_status = status
    step.healing_suggestion = message
    step.healing_at = datetime.now(timezone.utc)
    await db.commit()


async def _safe_publish(
    run_id: int,
    step: StepResult,
    status: str,
    suggestion: str | None,
    *,
    cache_hit: bool = False,
) -> None:
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
                "cache_hit": cache_hit,
            },
        )
    except Exception:
        return  # best-effort


# ── 多 step 综合分析（iter3）────────────────────────────────────
_RUN_MIN_FAILED_STEPS = 2  # 失败 step 少于该阈值时不触发综合分析


def apply_run_healing_hook(run: TestRun, failed_step_count: int) -> bool:
    """run 完成时决定是否触发综合分析。

    返回 True 表示调用方应在 commit 后 enqueue diagnose_run_failure。
    本函数同时就地写 run.result_summary["healing"]={status: "pending" 或 "skipped"}。
    """
    if not settings.AI_HEALING_ENABLED:
        return False
    if failed_step_count < _RUN_MIN_FAILED_STEPS:
        return False
    summary = dict(run.result_summary or {})
    summary["healing"] = {"status": "pending", "suggestion": None, "at": None, "cache_hit": False}
    run.result_summary = summary
    return True


def enqueue_run_diagnosis(run_id: int) -> None:
    try:
        from app.worker.tasks_healing import diagnose_run_failure

        diagnose_run_failure.delay(run_id)
    except Exception:
        logger.exception("enqueue diagnose_run_failure failed for run_id=%s", run_id)


async def maybe_enqueue_run_healing(db: AsyncSession, run: TestRun) -> None:
    """executor 在 run.status 最终 commit 之后调用：
    扫 run 的 failed/error step 数，决定是否触发综合诊断 + 标 healing pending。
    """
    if not settings.AI_HEALING_ENABLED:
        return
    result = await db.execute(
        select(StepResult.id).where(
            StepResult.run_id == run.id,
            StepResult.status.in_([RunStatus.failed, RunStatus.error]),
        )
    )
    failed_count = len(result.scalars().all())
    if not apply_run_healing_hook(run, failed_count):
        return
    await db.commit()
    enqueue_run_diagnosis(run.id)


def _make_run_cache_key(case_type: str, step_error_hashes: list[str]) -> str:
    """run 级 cache key：case_type + sorted(失败 step 错误 hash 列表)。"""
    payload = case_type + "|" + ",".join(sorted(step_error_hashes))
    digest = hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()
    return f"{_CACHE_KEY_PREFIX}run:{digest[:32]}"


def build_run_healing_prompt(
    *,
    case_type: str,
    case_name: str,
    failed_steps: list[StepResult],
    run_summary: dict | None = None,
) -> str:
    """综合多个失败 step 的 prompt：列出每个失败 step 的简要错误 + 整体特征。"""
    parts = [
        f"# 用例类型: {case_type}",
        f"# 用例名称: {case_name}",
        f"# 失败步骤数: {len(failed_steps)}",
    ]
    for s in failed_steps:
        parts.append(f"\n## 步骤 #{s.step_index + 1} {s.name}\n错误: {_truncate(s.error_message, limit=600)}")
    if run_summary:
        parts.append(f"\n# 运行摘要:\n{_truncate(run_summary, limit=500)}")
    parts.append(
        "\n请基于以上多个失败步骤的共同特征，给出："
        "\n1) 是否存在共性根因（如统一的环境/数据/前置问题）"
        "\n2) 修复优先级建议（先修哪个步骤最能止血）"
        "\n3) 若是独立失败，简短列出每个的最可能原因"
        "\n用中文回答，控制在 300 字以内。"
    )
    return "\n\n".join(parts)


async def run_diagnosis_for_run(db: AsyncSession, run_id: int) -> None:
    """综合诊断单个 run 内所有失败 step。

    幂等：若 run.result_summary["healing"]["status"] 已为 done/failed/skipped，直接返回。
    """
    from app.core.encryption import decrypt
    from app.models.ai_llm_config import AILLMConfig
    from app.models.project import Module, Project
    from app.services.ai_case.llm_client import LLMRequest, call_llm

    run = await db.get(TestRun, run_id)
    if run is None:
        return

    summary = dict(run.result_summary or {})
    current = summary.get("healing") or {}
    if current.get("status") in ("done", "failed", "skipped"):
        return  # 幂等

    case = await db.get(TestCase, run.case_id)
    if case is None:
        await _finalize_run_healing(db, run, status="failed", suggestion="case 已删除", cache_hit=False)
        return

    module = await db.get(Module, case.module_id)
    project = await db.get(Project, module.project_id) if module else None

    if project is None or project.ai_llm_config_id is None:
        await _finalize_run_healing(db, run, status="skipped", suggestion=None, cache_hit=False)
        await _safe_publish_run(run.id, "skipped", None, cache_hit=False)
        return

    config = await db.get(AILLMConfig, project.ai_llm_config_id)
    if config is None or not config.enabled:
        await _finalize_run_healing(db, run, status="skipped", suggestion=None, cache_hit=False)
        await _safe_publish_run(run.id, "skipped", None, cache_hit=False)
        return

    # 拉所有失败 step
    result = await db.execute(
        select(StepResult).where(
            StepResult.run_id == run_id,
            StepResult.status.in_([RunStatus.failed, RunStatus.error]),
        )
    )
    failed_steps = list(result.scalars().all())
    if len(failed_steps) < _RUN_MIN_FAILED_STEPS:
        # 失败 step 不足 → skipped（理论上不应到这里，executor hook 已过滤）
        await _finalize_run_healing(db, run, status="skipped", suggestion=None, cache_hit=False)
        await _safe_publish_run(run.id, "skipped", None, cache_hit=False)
        return

    case_type = case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type)
    # cache key 用每个 step 单独 hash 后排序，避免 step 顺序影响命中
    step_hashes: list[str] = []
    for s in failed_steps:
        response_status = None
        if isinstance(s.response_data, dict):
            response_status = s.response_data.get("status_code")
        sub = _make_cache_key(case_type, s.name, s.error_message, response_status)
        step_hashes.append(sub.split(":")[-1])

    cache_key = _make_run_cache_key(case_type, step_hashes)
    cached = await _get_cached_suggestion(cache_key)
    if cached:
        await _finalize_run_healing(db, run, status="done", suggestion=cached, cache_hit=True)
        await _safe_publish_run(run.id, "done", cached, cache_hit=True)
        return

    if not await _check_and_incr_daily_limit():
        await _finalize_run_healing(db, run, status="skipped", suggestion="daily-limit-reached", cache_hit=False)
        await _safe_publish_run(run.id, "skipped", "daily-limit-reached", cache_hit=False)
        return

    try:
        api_key = (
            ""
            if getattr(config, "provider", None) == "ollama" and not config.api_key_encrypted
            else decrypt(config.api_key_encrypted)
        )
    except Exception:
        await _finalize_run_healing(db, run, status="failed", suggestion="LLM API key 解密失败", cache_hit=False)
        await _safe_publish_run(run.id, "failed", "LLM API key 解密失败", cache_hit=False)
        return

    prompt = build_run_healing_prompt(
        case_type=case_type,
        case_name=case.name,
        failed_steps=failed_steps,
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
        logger.warning("AI run healing LLM call failed: %s", exc)
        await _finalize_run_healing(db, run, status="failed", suggestion=f"LLM 调用失败: {exc}", cache_hit=False)
        await _safe_publish_run(run.id, "failed", str(exc), cache_hit=False)
        return

    text = (response.text or "").strip() or "（LLM 未返回内容）"
    await _finalize_run_healing(db, run, status="done", suggestion=text, cache_hit=False)
    await _write_cached_suggestion(cache_key, text)
    await _safe_publish_run(run.id, "done", text, cache_hit=False)


async def _finalize_run_healing(
    db: AsyncSession,
    run: TestRun,
    *,
    status: str,
    suggestion: str | None,
    cache_hit: bool,
) -> None:
    summary = dict(run.result_summary or {})
    summary["healing"] = {
        "status": status,
        "suggestion": suggestion,
        "at": datetime.now(timezone.utc).isoformat(),
        "cache_hit": cache_hit,
    }
    run.result_summary = summary
    await db.commit()


async def _safe_publish_run(
    run_id: int,
    status: str,
    suggestion: str | None,
    *,
    cache_hit: bool = False,
) -> None:
    from app.core.redis_client import publish_run_event

    try:
        await publish_run_event(
            run_id,
            {
                "type": "run_healing_suggestion",
                "run_id": run_id,
                "status": status,
                "suggestion": suggestion,
                "cache_hit": cache_hit,
            },
        )
    except Exception:
        return  # best-effort
