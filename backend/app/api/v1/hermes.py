"""Hermes project retrieval API."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, time, timedelta, timezone
from time import perf_counter
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.encryption import decrypt
from app.core.database import get_db
from app.models.ai_llm_config import AILLMConfig
from app.models.case import TestCase
from app.models.case import TestRun
from app.models.hermes import HermesSession
from app.models.bootstrap import load_all_models
from app.models.knowledge import KnowledgeEntry
from app.models.project import Module, Project
from app.models.requirement import TestRequirement
from app.models.plan import PlanStatus, ScheduleType, TestPlan
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.hermes import (
    HermesDraftConfirmIn,
    HermesDraftIn,
    HermesEvaluationSetOut,
    HermesFeedbackIn,
    HermesGovernanceSummaryOut,
    HermesQueryIn,
    HermesQueryOut,
    HermesSessionCreateIn,
    HermesSessionOut,
    HermesSourceOut,
    HermesToolIn,
)
from app.schemas.hermes_orchestration import (
    HermesOrchestrationIn,
    HermesOrchestrationOut,
    HermesOrchestrationPlanOut,
    HermesOrchestrationStepOut,
)
from app.schemas.hermes_tools import HermesToolCallIn, HermesToolCatalogOut, HermesToolOut, HermesToolStatus
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_governance import (
    check_and_incr_daily_limit,
    llm_extra_params,
    redact_llm_text,
    resolve_system_prompt,
)
from app.services.audit import write_audit_log
from app.services.knowledge import redact_knowledge_text
from app.services.hermes import (
    HERMES_SYSTEM_PROMPT,
    HERMES_EVALUATION_SET,
    HERMES_EVALUATION_SET_ID,
    HERMES_EVALUATION_SET_VERSION,
    HERMES_PROMPT_VERSION,
    HermesCandidate,
    HermesHistoryContext,
    HermesRankedSource,
    build_governance_summary,
    build_answer,
    build_grounded_prompt,
    build_history_context,
    has_valid_source_citation,
    rank_candidates,
)
from app.services.hermes_tools import (
    HERMES_TOOL_TIMEOUT_MAX_MS,
    execute_read_tool,
    parse_tool_arguments,
    tool_catalog,
)
from app.services.hermes_orchestration import HermesToolOutcome, plan_read_tools, summarize_tool_outcomes


logger = logging.getLogger(__name__)

router = APIRouter(tags=["智能中枢"])

load_all_models()


def _updated_bounds(body: HermesQueryIn) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(body.updated_from, time.min, tzinfo=timezone.utc) if body.updated_from else None
    end = (
        datetime.combine(body.updated_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        if body.updated_to
        else None
    )
    return start, end


@router.get("/hermes/tools", response_model=HermesToolCatalogOut)
async def list_hermes_tools(user: User = Depends(get_current_user)):
    """Expose the allow-listed read-only tools to an authenticated client."""

    _ = user
    return HermesToolCatalogOut(tools=tool_catalog(), generated_at=datetime.now(timezone.utc))


@router.post("/hermes/tools/execute", response_model=HermesToolOut)
async def execute_hermes_tool(
    body: HermesToolCallIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run one bounded, project-scoped, read-only Hermes tool."""

    await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    try:
        arguments = parse_tool_arguments(body.tool, body.arguments)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="工具参数无效") from exc

    started_at = perf_counter()
    execution = None
    status: HermesToolStatus = "error"
    message: str | None = "工具执行失败"
    try:
        timeout_seconds = min(body.timeout_ms, HERMES_TOOL_TIMEOUT_MAX_MS) / 1_000
        execution = await asyncio.wait_for(
            execute_read_tool(db, user, body.project_id, body.tool, arguments),
            timeout=timeout_seconds,
        )
        status = execution.status
        message = execution.message
    except TimeoutError:
        status = "timeout"
        message = "工具执行超时，请缩小查询范围后重试"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Hermes read tool failed: tool=%s project_id=%s error_type=%s",
            body.tool,
            body.project_id,
            type(exc).__name__,
        )
    duration_ms = max(0, round((perf_counter() - started_at) * 1_000))

    try:
        await db.rollback()
        await write_audit_log(
            db,
            action="hermes_read_tool",
            resource_type="hermes_tool",
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            ip_address=request.client.host if request.client else "",
            detail=f"tool={body.tool};status={status};duration_ms={duration_ms}",
        )
        await db.commit()
    except Exception:  # noqa: BLE001
        await db.rollback()
        logger.warning("Failed to persist Hermes read-tool audit", exc_info=True)

    return HermesToolOut(
        project_id=body.project_id,
        conversation_id=body.conversation_id,
        tool=body.tool,
        status=status,
        duration_ms=duration_ms,
        message=message,
        data=execution.data if execution else {},
        evidence=execution.evidence if execution else [],
        generated_at=datetime.now(timezone.utc),
    )


@router.post("/hermes/orchestrate", response_model=HermesOrchestrationOut)
async def orchestrate_hermes(
    body: HermesOrchestrationIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Route a natural-language request to at most two bounded read tools."""

    await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    routing = plan_read_tools(body.query)
    plans = [
        HermesOrchestrationPlanOut(tool=item.tool, arguments=item.arguments, reason=item.reason)
        for item in routing.plans
    ]
    if routing.status != "matched":
        answer = routing.clarification or "当前问题未命中可自动读取的只读工具，我会改用项目证据检索继续回答。"
        return HermesOrchestrationOut(
            project_id=body.project_id,
            conversation_id=body.conversation_id,
            query=body.query,
            status=routing.status,
            clarification=routing.clarification,
            plans=plans,
            steps=[],
            answer=answer,
            generated_at=datetime.now(timezone.utc),
        )

    started_at = perf_counter()
    steps: list[HermesOrchestrationStepOut] = []
    outcomes: list[HermesToolOutcome] = []
    for plan in routing.plans:
        result = await execute_hermes_tool(
            HermesToolCallIn(
                project_id=body.project_id,
                conversation_id=body.conversation_id,
                tool=plan.tool,
                arguments=plan.arguments,
                timeout_ms=HERMES_TOOL_TIMEOUT_MAX_MS,
            ),
            request,
            db,
            user,
        )
        steps.append(
            HermesOrchestrationStepOut(
                tool=result.tool,
                arguments=plan.arguments,
                status=result.status,
                duration_ms=result.duration_ms,
                message=result.message,
                data=result.data,
                evidence=result.evidence,
            )
        )
        outcomes.append(HermesToolOutcome(tool=result.tool, status=result.status, data=result.data))

    answer = summarize_tool_outcomes(outcomes)
    session = await _get_or_create_session(
        db,
        user,
        HermesQueryIn(
            project_id=body.project_id,
            query=body.query,
            conversation_id=body.conversation_id,
            session_id=body.session_id,
        ),
    )
    generated_at = datetime.now(timezone.utc)
    latency_ms = max(0, round((perf_counter() - started_at) * 1_000))
    evidence = [item.model_dump() for step in steps for item in step.evidence]
    messages = list(session.messages) if isinstance(session.messages, list) else []
    messages.extend(
        [
            {"role": "user", "content": redact_knowledge_text(body.query, limit=2_000), "at": generated_at.isoformat()},
            {
                "role": "assistant",
                "content": answer,
                "mode": "project_retrieval",
                "sources": evidence,
                "tool": "hermes_orchestrator",
                "tool_steps": [{"tool": step.tool, "status": step.status} for step in steps],
                "prompt_version": HERMES_PROMPT_VERSION,
                "latency_ms": latency_ms,
                "at": generated_at.isoformat(),
            },
        ]
    )
    session.messages = messages[-40:]
    context_filters = dict(session.context_filters) if isinstance(session.context_filters, dict) else {}
    context_filters["conversation_id"] = body.conversation_id
    session.context_filters = context_filters
    metrics = dict(session.metrics) if isinstance(session.metrics, dict) else {}
    metrics["queries"] = _safe_increment(metrics.get("queries"), 1)
    metrics["orchestration_calls"] = _safe_increment(metrics.get("orchestration_calls"), 1)
    metrics["tool_calls"] = _safe_increment(metrics.get("tool_calls"), len(steps))
    metrics["last_latency_ms"] = latency_ms
    session.metrics = metrics
    await db.commit()
    return HermesOrchestrationOut(
        project_id=body.project_id,
        conversation_id=body.conversation_id,
        query=body.query,
        status="matched",
        plans=plans,
        steps=steps,
        answer=answer,
        generated_at=generated_at,
        session_id=session.id,
        message_index=len(session.messages) - 1,
    )


async def _llm_answer(
    db: AsyncSession,
    project: Project,
    query: str,
    sources: list[HermesRankedSource],
    history_context: HermesHistoryContext,
) -> str | None:
    """Generate a grounded answer when the project has an enabled AI config."""

    config_id = getattr(project, "ai_llm_config_id", None)
    if not sources or not config_id:
        return None
    config = await db.get(AILLMConfig, config_id)
    if config is None or not config.enabled:
        return None
    try:
        api_key = (
            "" if config.provider == "ollama" and not config.api_key_encrypted else decrypt(config.api_key_encrypted)
        )
        if not await check_and_incr_daily_limit(config=config, capability="hermes_query"):
            return None
        response = await call_llm(
            LLMRequest(
                provider=config.provider,
                api_key=api_key,
                model_name=config.model_name,
                prompt=build_grounded_prompt(redact_knowledge_text(query, limit=2_000) or "", sources, history_context),
                endpoint=config.endpoint,
                system_prompt=resolve_system_prompt(config, "hermes_query", HERMES_SYSTEM_PROMPT),
                timeout_seconds=60.0,
                extra_params=llm_extra_params(config),
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hermes LLM query failed: config_id=%s error_type=%s", config.id, type(exc).__name__)
        return None

    answer = redact_llm_text(response.text, limit=4_000).strip()
    if not has_valid_source_citation(answer, len(sources)):
        logger.warning("Hermes LLM query returned no valid source citation: config_id=%s", config.id)
        return None
    return answer


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _safe_increment(value: object, amount: int) -> int:
    try:
        current = int(value) if isinstance(value, (int, str)) else 0
    except (TypeError, ValueError):
        current = 0
    return max(0, current) + max(0, amount)


def _knowledge_candidates(rows: Sequence[Any], project_id: int) -> list[HermesCandidate]:
    return [
        HermesCandidate(
            source_type="knowledge",
            source_id=entry.id,
            project_id=entry.project_id,
            title=entry.title,
            body="\n".join(value for value in (entry.summary, entry.content) if value),
            source_ref=entry.source_ref or f"KNOWLEDGE-{entry.id}",
            path=f"/knowledge?project_id={project_id}&knowledge_id={entry.id}",
            tags=tuple(entry.tags or []),
            updated_at=entry.updated_at or entry.created_at,
        )
        for entry, _project_name in rows
    ]


def _requirement_candidates(rows: Sequence[Any], project_id: int) -> list[HermesCandidate]:
    return [
        HermesCandidate(
            source_type="requirement",
            source_id=requirement.id,
            project_id=requirement.project_id,
            title=requirement.title,
            body="\n".join(
                value
                for value in (
                    requirement.description,
                    " ".join(str(item.get("text", "")) for item in (requirement.acceptance_criteria or [])),
                )
                if value
            ),
            source_ref=requirement.requirement_code or f"REQ-{requirement.id}",
            path=f"/requirements?project_id={project_id}&requirement_id={requirement.id}",
            tags=(requirement.priority, requirement.status),
            updated_at=requirement.updated_at or requirement.created_at,
        )
        for requirement, _project_name in rows
    ]


def _case_candidates(rows: Sequence[Any]) -> list[HermesCandidate]:
    return [
        HermesCandidate(
            source_type="case",
            source_id=case.id,
            project_id=module.project_id,
            title=case.name,
            body="\n".join(value for value in (case.summary, case.description) if value),
            source_ref=case.case_code,
            path=f"/cases?project_id={module.project_id}&case_id={case.id}",
            tags=tuple(case.tags or []) + (_enum_value(case.case_type), case.priority, case.case_level),
            updated_at=case.updated_at or case.created_at,
        )
        for case, module in rows
    ]


async def _get_or_create_session(db: AsyncSession, user: User, body: HermesQueryIn) -> HermesSession:
    if body.session_id is not None:
        session = await db.get(HermesSession, body.session_id)
        if session is None or session.project_id != body.project_id or session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Hermes 会话不存在")
        return session
    session = HermesSession(
        project_id=body.project_id,
        user_id=user.id,
        title=body.query[:80],
        context_filters={"source_types": body.source_types},
        messages=[],
        drafts=[],
        metrics={"queries": 0, "tool_calls": 0, "helpful": 0, "not_helpful": 0},
    )
    db.add(session)
    await db.flush()
    return session


async def _owned_session(db: AsyncSession, user: User, session_id: int, project_id: int) -> HermesSession:
    session = await db.get(HermesSession, session_id)
    if session is None or session.project_id != project_id or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Hermes 会话不存在")
    return session


@router.post("/hermes/query", response_model=HermesQueryOut)
async def query_hermes(
    body: HermesQueryIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    started_at = perf_counter()
    await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    session = await _get_or_create_session(db, user, body)

    updated_from, updated_to = _updated_bounds(body)
    selected_types = set(body.source_types)
    knowledge_rows: Sequence[Any] = []
    requirement_rows: Sequence[Any] = []
    case_rows: Sequence[Any] = []
    if not selected_types or "knowledge" in selected_types:
        knowledge_query = (
            select(KnowledgeEntry, Project.name)
            .outerjoin(Project, Project.id == KnowledgeEntry.project_id)
            .where(
                or_(
                    KnowledgeEntry.project_id == body.project_id,
                    and_(KnowledgeEntry.project_id.is_(None), KnowledgeEntry.status == "published"),
                )
            )
        )
        if updated_from:
            knowledge_query = knowledge_query.where(KnowledgeEntry.updated_at >= updated_from)
        if updated_to:
            knowledge_query = knowledge_query.where(KnowledgeEntry.updated_at < updated_to)
        knowledge_query = knowledge_query.order_by(KnowledgeEntry.updated_at.desc(), KnowledgeEntry.id.desc()).limit(
            200
        )
        knowledge_rows = (await db.execute(knowledge_query)).all()
    if not selected_types or "requirement" in selected_types:
        requirement_query = (
            select(TestRequirement, Project.name)
            .join(Project, Project.id == TestRequirement.project_id)
            .where(TestRequirement.project_id == body.project_id)
        )
        if updated_from:
            requirement_query = requirement_query.where(TestRequirement.updated_at >= updated_from)
        if updated_to:
            requirement_query = requirement_query.where(TestRequirement.updated_at < updated_to)
        requirement_query = requirement_query.order_by(
            TestRequirement.updated_at.desc(), TestRequirement.id.desc()
        ).limit(200)
        requirement_rows = (await db.execute(requirement_query)).all()
    if not selected_types or "case" in selected_types:
        case_query = (
            select(TestCase, Module)
            .join(Module, Module.id == TestCase.module_id)
            .where(Module.project_id == body.project_id)
        )
        if updated_from:
            case_query = case_query.where(TestCase.updated_at >= updated_from)
        if updated_to:
            case_query = case_query.where(TestCase.updated_at < updated_to)
        case_query = case_query.order_by(TestCase.updated_at.desc(), TestCase.id.desc()).limit(300)
        case_rows = (await db.execute(case_query)).all()

    candidates = (
        _knowledge_candidates(knowledge_rows, body.project_id)
        + _requirement_candidates(requirement_rows, body.project_id)
        + _case_candidates(case_rows)
    )
    sources = rank_candidates(
        body.query,
        candidates,
        body.limit,
        source_types=body.source_types,
        updated_from=body.updated_from,
        updated_to=body.updated_to,
    )
    history_turns = [(item.role, item.content) for item in body.history]
    if not history_turns:
        history_turns = [
            (str(item.get("role")), str(item.get("content")))
            for item in (session.messages or [])[-12:]
            if item.get("role") in {"user", "assistant"} and str(item.get("content") or "").strip()
        ]
    history_context = build_history_context(history_turns, body.context_budget)
    answer, raw_mode = build_answer(sources)
    mode: Literal["llm_grounded", "project_retrieval", "no_results"] = cast(
        Literal["llm_grounded", "project_retrieval", "no_results"], raw_mode
    )
    llm_answer = await _llm_answer(db, project, body.query, sources, history_context)
    if llm_answer:
        answer, mode = llm_answer, "llm_grounded"
    generated_at = datetime.now(timezone.utc)
    latency_ms = int((perf_counter() - started_at) * 1000)
    messages = list(session.messages or [])
    messages.extend(
        [
            {"role": "user", "content": redact_knowledge_text(body.query, limit=2_000), "at": generated_at.isoformat()},
            {
                "role": "assistant",
                "content": answer,
                "mode": mode,
                "sources": [
                    {**asdict(source), "updated_at": source.updated_at.isoformat() if source.updated_at else None}
                    for source in sources
                ],
                "tool": "project_evidence_search",
                "prompt_version": HERMES_PROMPT_VERSION,
                "latency_ms": latency_ms,
                "at": generated_at.isoformat(),
            },
        ]
    )
    session.messages = messages[-40:]
    session.context_filters = {
        "conversation_id": body.conversation_id,
        "source_types": body.source_types,
        "updated_from": body.updated_from.isoformat() if body.updated_from else None,
        "updated_to": body.updated_to.isoformat() if body.updated_to else None,
        "context_budget": body.context_budget,
    }
    metrics = dict(session.metrics or {})
    metrics["queries"] = int(metrics.get("queries", 0)) + 1
    metrics["last_latency_ms"] = latency_ms
    session.metrics = metrics
    await db.commit()
    return HermesQueryOut(
        project_id=body.project_id,
        query=body.query,
        conversation_id=body.conversation_id,
        history_used=len(history_context.turns),
        history_omitted=history_context.omitted,
        context_chars=history_context.chars,
        context_budget=body.context_budget,
        source_types=list(body.source_types),
        updated_from=body.updated_from,
        updated_to=body.updated_to,
        mode=mode,
        answer=answer,
        sources=[HermesSourceOut(**asdict(source)) for source in sources],
        generated_at=generated_at,
        session_id=session.id,
        message_index=len(session.messages) - 1,
        latency_ms=latency_ms,
    )


@router.get("/hermes/sessions", response_model=list[HermesSessionOut])
async def list_hermes_sessions(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    query = (
        select(HermesSession)
        .where(HermesSession.project_id == project_id, HermesSession.user_id == user.id)
        .order_by(HermesSession.updated_at.desc())
        .limit(50)
    )
    return (await db.execute(query)).scalars().all()


@router.post("/hermes/sessions", response_model=HermesSessionOut, status_code=201)
async def create_hermes_session(
    body: HermesSessionCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    session = HermesSession(
        project_id=body.project_id,
        user_id=user.id,
        title=body.title,
        context_filters={},
        messages=[],
        drafts=[],
        metrics={"queries": 0, "tool_calls": 0, "helpful": 0, "not_helpful": 0},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/hermes/governance/summary", response_model=HermesGovernanceSummaryOut)
async def hermes_governance_summary(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    rows = (
        (await db.execute(select(HermesSession).where(HermesSession.project_id == project_id).limit(500)))
        .scalars()
        .all()
    )
    return build_governance_summary(rows)


@router.get("/hermes/governance/evaluation-set", response_model=HermesEvaluationSetOut)
async def hermes_evaluation_set(user: User = Depends(get_current_user)):
    """Return the bounded, non-project-specific H5 evaluation prompts."""

    _ = user
    return {
        "id": HERMES_EVALUATION_SET_ID,
        "version": HERMES_EVALUATION_SET_VERSION,
        "questions": list(HERMES_EVALUATION_SET),
    }


@router.post("/hermes/sessions/{session_id}/tools/{tool_name}")
async def run_hermes_readonly_tool(
    session_id: int,
    tool_name: str,
    body: HermesToolIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    session = await _owned_session(db, user, session_id, body.project_id)
    if tool_name == "failed_runs":
        query = (
            select(TestRun)
            .join(TestCase, TestCase.id == TestRun.case_id)
            .join(Module, Module.id == TestCase.module_id)
            .where(Module.project_id == body.project_id, TestRun.status.in_(["failed", "error"]))
            .order_by(TestRun.created_at.desc())
            .limit(max(1, min(int(body.arguments.get("limit", 10)), 50)))
        )
        rows = (await db.execute(query)).scalars().all()
        result = [
            {
                "run_id": row.id,
                "case_id": row.case_id,
                "status": _enum_value(row.status),
                "error": redact_llm_text(row.error_message or "", limit=500),
            }
            for row in rows
        ]
    elif tool_name == "quality_summary":
        query = (
            select(TestRun)
            .join(TestCase, TestCase.id == TestRun.case_id)
            .join(Module, Module.id == TestCase.module_id)
            .where(Module.project_id == body.project_id)
            .order_by(TestRun.created_at.desc())
            .limit(500)
        )
        rows = (await db.execute(query)).scalars().all()
        statuses = [_enum_value(row.status) for row in rows]
        passed = statuses.count("passed")
        result = {"total": len(rows), "passed": passed, "pass_rate": round(passed / len(rows) * 100, 2) if rows else 0}
    else:
        raise HTTPException(status_code=404, detail="Hermes 只读工具不存在")
    messages = list(session.messages or [])
    messages.append(
        {
            "role": "tool",
            "tool": tool_name,
            "arguments": body.arguments,
            "result": result,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    session.messages = messages[-40:]
    metrics = dict(session.metrics or {})
    metrics["tool_calls"] = int(metrics.get("tool_calls", 0)) + 1
    session.metrics = metrics
    await db.commit()
    return {"session_id": session.id, "tool": tool_name, "result": result}


@router.post("/hermes/sessions/{session_id}/drafts")
async def create_hermes_draft(
    session_id: int,
    body: HermesDraftIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    session = await _owned_session(db, user, session_id, body.project_id)
    draft = {
        "id": uuid.uuid4().hex,
        "draft_type": body.draft_type,
        "payload": body.payload,
        "sources": body.sources,
        "status": "pending_confirmation",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    session.drafts = [*(session.drafts or []), draft][-20:]
    await db.commit()
    return draft


@router.post("/hermes/sessions/{session_id}/drafts/confirm")
async def confirm_hermes_draft(
    session_id: int,
    body: HermesDraftConfirmIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    session = await _owned_session(db, user, session_id, body.project_id)
    drafts = list(session.drafts or [])
    draft = next((item for item in drafts if item.get("id") == body.draft_id), None)
    if draft is None or draft.get("status") != "pending_confirmation":
        raise HTTPException(status_code=409, detail="Hermes 草稿不存在或已处理")
    payload = draft.get("payload") if isinstance(draft.get("payload"), dict) else {}
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="测试计划草稿缺少名称")
    plan = TestPlan(
        name=name[:256],
        description=str(payload.get("objective") or "")[:4000] or None,
        project_id=body.project_id,
        suite_ids=[],
        schedule_type=ScheduleType.manual,
        status=PlanStatus.draft,
        is_enabled=False,
        auto_create_bugs=False,
        config={"hermes_sources": draft.get("sources") or [], "test_points": payload.get("testPoints") or []},
        creator_id=user.id,
    )
    db.add(plan)
    await db.flush()
    draft["status"] = "confirmed"
    draft["plan_id"] = plan.id
    draft["confirmed_at"] = datetime.now(timezone.utc).isoformat()
    session.drafts = drafts
    await db.commit()
    return {"draft_id": draft["id"], "status": "confirmed", "plan_id": plan.id}


@router.post("/hermes/sessions/{session_id}/feedback")
async def submit_hermes_feedback(
    session_id: int,
    body: HermesFeedbackIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    session = await _owned_session(db, user, session_id, body.project_id)
    messages = list(session.messages or [])
    if body.message_index >= len(messages) or messages[body.message_index].get("role") != "assistant":
        raise HTTPException(status_code=422, detail="只能评价 Hermes 助手消息")
    messages[body.message_index] = {
        **messages[body.message_index],
        "feedback": body.rating,
        "feedback_comment": body.comment,
    }
    session.messages = messages
    metrics = dict(session.metrics or {})
    metrics[body.rating] = int(metrics.get(body.rating, 0)) + 1
    session.metrics = metrics
    await db.commit()
    return {"session_id": session.id, "message_index": body.message_index, "rating": body.rating}
