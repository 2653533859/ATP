"""Dedicated conversational AI chat with streaming (SSE) support."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.api.v1.cases.common import _generate_case_code, _get_module_for_case_code
from app.api.v1.cases.runs import trigger_run
from app.api.v1.statistics import invalidate_stats_cache
from app.api.v1.suites import trigger_suite_run
from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import decrypt
from app.models.ai_llm_config import AILLMConfig
from app.models.case import TestCase
from app.models.defect import Defect
from app.models.knowledge import KnowledgeEntry
from app.models.project import Module, Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.case import RunTriggerRequest
from app.schemas.suite import SuiteRunTrigger
from app.services.ai_case.agent_chat import (
    ChatActionType,
    build_agent_system_prompt,
    default_case_status,
    extract_completed_proposal,
    gather_project_context_for_chat,
    normalize_case_type,
    split_stream_action_tag,
)
from app.services.ai_case.llm_client import LLMRequest, stream_llm
from app.services.ai_governance import check_and_incr_daily_limit, llm_extra_params
from app.services.audit import write_audit_log
from app.services.local_artifact_cleanup import case_run_ids, delete_run_artifacts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/chat", tags=["AI 自由对话"])


class AiChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=5_000)


class AiChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5_000)
    project_id: int | None = None
    history: list[AiChatMessage] = Field(default_factory=list, max_length=20)


async def _resolve_active_llm(db: AsyncSession, project_id: int | None) -> tuple[AILLMConfig | None, str]:
    config: AILLMConfig | None = None
    if project_id:
        project = await db.get(Project, project_id)
        if project and project.ai_llm_config_id:
            candidate = await db.get(AILLMConfig, project.ai_llm_config_id)
            if candidate and candidate.enabled:
                config = candidate

    if not config:
        res = await db.execute(
            select(AILLMConfig).where(AILLMConfig.enabled == True).order_by(AILLMConfig.id.desc()).limit(1)
        )
        config = res.scalars().first()

    if not config or not config.enabled:
        return None, ""

    api_key = "" if config.provider == "ollama" and not config.api_key_encrypted else decrypt(config.api_key_encrypted)
    return config, api_key


_CHAT_SYSTEM_PROMPT = (
    "你是一个专业、智能、随和的全栈测试与软件工程 AI 助手（Hermes）。"
    "你可以与用户自由畅聊，解答关于测试策略、用例设计、Python/TypeScript 编程、自动化架构、排障调试等各类技术疑问，"
    "也可以进行轻松的日常闲聊交流。请语言亲切自然、条理清晰，使用标准 Markdown 格式（包含标题、列表、代码块）进行排版输出。"
)


class AiChatExecuteActionIn(BaseModel):
    project_id: int = Field(ge=1)
    action: ChatActionType
    params: dict[str, Any] = Field(default_factory=dict)


class AiChatExecuteActionOut(BaseModel):
    ok: bool = True
    action: ChatActionType
    message: str
    resource_id: int | None = None
    route: str | None = None


@router.post("/stream")
async def chat_stream(
    body: AiChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """流式返回统一 Hermes 智能对话内容 (SSE)，支持项目数据感知与操作提案。"""
    if body.project_id is not None:
        await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    config, api_key = await _resolve_active_llm(db, body.project_id)

    async def event_generator():
        if not config:
            fallback = (
                "当前平台尚未配置可用的大语言模型。请管理员前往「系统 ➔ AI 模型配置」"
                "添加并启用模型，即可开启智能对话。"
            )
            yield f"data: {json.dumps({'token': fallback}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not await check_and_incr_daily_limit(config=config, capability="ai_chat"):
            yield f"data: {json.dumps({'error': '已达模型每日调用上限，请明日重试或联系管理员提升配额'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        project_context_block = ""
        if body.project_id is not None:
            project_context_block, tool_events = await gather_project_context_for_chat(
                db, user, body.project_id, body.query
            )
            for evt in tool_events:
                yield (
                    "data: "
                    + json.dumps(
                        {"tool_event": {"tool": evt.tool, "label": evt.label, "summary": evt.summary}},
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

        history_lines = []
        for item in body.history[-10:]:
            prefix = "用户" if item.role == "user" else "助手"
            history_lines.append(f"{prefix}: {item.content}")
        history_block = "\n".join(history_lines)

        prompt_parts: list[str] = []
        if project_context_block:
            prompt_parts.append(f"当前项目真实数据上下文：\n{project_context_block}")
        if history_block:
            prompt_parts.append(f"历史对话：\n{history_block}")
        prompt_parts.append(f"当前用户问题：{body.query}")
        user_prompt = "\n\n".join(prompt_parts)

        request = LLMRequest(
            provider=config.provider,
            api_key=api_key,
            model_name=config.model_name,
            prompt=user_prompt,
            endpoint=config.endpoint,
            system_prompt=build_agent_system_prompt(body.project_id is not None),
            timeout_seconds=90.0,
            extra_params=llm_extra_params(config),
        )

        buffer = ""
        inside_action_tag = False
        try:
            async for token in stream_llm(request):
                buffer += token
                if inside_action_tag:
                    continue
                emit_text, remainder, entered_tag = split_stream_action_tag(buffer)
                buffer = remainder
                inside_action_tag = entered_tag
                if emit_text:
                    yield f"data: {json.dumps({'token': emit_text}, ensure_ascii=False)}\n\n"

            if not inside_action_tag and buffer:
                yield f"data: {json.dumps({'token': buffer}, ensure_ascii=False)}\n\n"
            elif inside_action_tag:
                proposal = extract_completed_proposal(buffer)
                if proposal:
                    yield f"data: {json.dumps({'action_proposal': proposal}, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI Chat stream failed: error=%s", type(exc).__name__)
            yield f"data: {json.dumps({'error': f'模型响应异常: {type(exc).__name__}'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _require_positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HTTPException(status_code=400, detail=f"缺少有效的 {field_name}")
    return value


@router.post("/execute-action", response_model=AiChatExecuteActionOut)
async def execute_chat_action(
    body: AiChatExecuteActionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """在用户确认后，执行 Hermes 对话中生成的项目操作。"""
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    params = body.params or {}

    if body.action == "run_case":
        raw_case_id = params.get("case_id")
        if not isinstance(raw_case_id, int) or raw_case_id < 1:
            raise HTTPException(status_code=400, detail="缺少有效的 case_id")
        env_id = params.get("env_id") if isinstance(params.get("env_id"), int) else None
        run = await trigger_run(
            raw_case_id,
            RunTriggerRequest(env_id=env_id),
            db=db,
            current_user=user,
        )
        await write_audit_log(
            db,
            action="hermes_chat_run_case",
            resource_type="test_run",
            resource_id=run.id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话触发执行用例 #{raw_case_id}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="run_case",
            message=f"已触发执行用例 #{raw_case_id}（运行 ID: #{run.id}）",
            resource_id=run.id,
            route=f"/runs/{run.id}",
        )

    if body.action == "run_suite":
        raw_suite_id = params.get("suite_id")
        if not isinstance(raw_suite_id, int) or raw_suite_id < 1:
            raise HTTPException(status_code=400, detail="缺少有效的 suite_id")
        env_id = params.get("env_id") if isinstance(params.get("env_id"), int) else None
        suite_run = await trigger_suite_run(
            raw_suite_id,
            SuiteRunTrigger(env_id=env_id),
            db=db,
            current_user=user,
        )
        await write_audit_log(
            db,
            action="hermes_chat_run_suite",
            resource_type="suite_run",
            resource_id=suite_run.id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话触发执行套件 #{raw_suite_id}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="run_suite",
            message=f"已触发执行套件 #{raw_suite_id}（套件运行 ID: #{suite_run.id}）",
            resource_id=suite_run.id,
            route="/suites",
        )

    if body.action == "update_case":
        raw_case_id = params.get("case_id")
        if not isinstance(raw_case_id, int) or raw_case_id < 1:
            raise HTTPException(status_code=400, detail="缺少有效的 case_id")
        case = await db.get(TestCase, raw_case_id)
        if not case:
            raise HTTPException(status_code=404, detail="用例不存在")
        module = await db.get(Module, case.module_id)
        if not module or module.project_id != body.project_id:
            raise HTTPException(status_code=404, detail="用例不属于当前项目")
        if isinstance(params.get("name"), str) and params["name"].strip():
            case.name = params["name"].strip()[:128]
        if isinstance(params.get("description"), str):
            case.description = params["description"].strip() or None
        if isinstance(params.get("steps"), list):
            next_config = dict(case.config or {})
            next_config["steps"] = params["steps"]
            case.config = next_config
        await write_audit_log(
            db,
            action="hermes_chat_update_case",
            resource_type="test_case",
            resource_id=case.id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话更新用例 #{case.id}：{case.name}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="update_case",
            message=f"已更新测试用例 #{case.id}：{case.name}",
            resource_id=case.id,
            route=f"/cases/{case.id}",
        )

    if body.action == "update_defect":
        raw_defect_id = params.get("defect_id")
        if not isinstance(raw_defect_id, int) or raw_defect_id < 1:
            raise HTTPException(status_code=400, detail="缺少有效的 defect_id")
        defect = await db.get(Defect, raw_defect_id)
        if not defect or defect.project_id != body.project_id:
            raise HTTPException(status_code=404, detail="缺陷不存在或不属于当前项目")
        next_status = str(params.get("status") or "").strip().lower()
        if next_status in {"open", "in_progress", "resolved", "closed"}:
            defect.status = next_status
        if isinstance(params.get("resolution"), str):
            defect.resolution = params["resolution"].strip()[:64] or None
        await write_audit_log(
            db,
            action="hermes_chat_update_defect",
            resource_type="defect",
            resource_id=defect.id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话更新缺陷 #{defect.id} 状态为 {defect.status}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="update_defect",
            message=f"已更新缺陷 #{defect.id} 状态为 {defect.status}",
            resource_id=defect.id,
            route="/bugs",
        )

    if body.action == "create_case":
        name = str(params.get("name") or "").strip()[:128]
        if not name:
            raise HTTPException(status_code=400, detail="缺少用例名称")
        module_id = params.get("module_id") if isinstance(params.get("module_id"), int) else None
        if module_id is not None:
            module = await db.get(Module, module_id)
            if not module or module.project_id != body.project_id:
                module_id = None
        if module_id is None:
            mod_res = await db.execute(
                select(Module.id).where(Module.project_id == body.project_id).order_by(Module.id.asc()).limit(1)
            )
            module_id = mod_res.scalar_one_or_none()
        if module_id is None:
            raise HTTPException(status_code=400, detail="当前项目尚无模块，请先创建模块")

        case_type = normalize_case_type(params.get("case_type"))
        steps = params.get("steps") if isinstance(params.get("steps"), list) else []

        module_obj = await _get_module_for_case_code(db, module_id)
        case_code = await _generate_case_code(db, module_obj, case_type)
        summary = str(params.get("summary") or params.get("description") or name).strip()[:512]

        case = TestCase(
            module_id=module_id,
            name=name,
            case_code=case_code,
            summary=summary,
            description=str(params.get("description") or "").strip() or None,
            case_type=case_type,
            status=default_case_status(),
            config={"steps": steps} if steps else {},
            creator_id=user.id,
        )
        db.add(case)
        await db.flush()
        await write_audit_log(
            db,
            action="hermes_chat_create_case",
            resource_type="test_case",
            resource_id=case.id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话创建用例: {case.name}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="create_case",
            message=f"已创建测试用例 #{case.id}：{case.name}",
            resource_id=case.id,
            route=f"/cases/{case.id}",
        )

    if body.action == "create_defect":
        title = str(params.get("title") or "").strip()[:256]
        if not title:
            raise HTTPException(status_code=400, detail="缺少缺陷标题")
        case_id = params.get("case_id") if isinstance(params.get("case_id"), int) else None
        priority = str(params.get("priority") or "P2").upper()
        if priority not in {"P0", "P1", "P2", "P3"}:
            priority = "P2"
        defect = Defect(
            project_id=body.project_id,
            case_id=case_id,
            title=title,
            description=str(params.get("description") or "").strip() or None,
            priority=priority,
            creator_id=user.id,
        )
        db.add(defect)
        await db.flush()
        await write_audit_log(
            db,
            action="hermes_chat_create_defect",
            resource_type="defect",
            resource_id=defect.id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话创建缺陷: {defect.title}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="create_defect",
            message=f"已创建缺陷 #{defect.id}：{defect.title}",
            resource_id=defect.id,
            route="/bugs",
        )

    if body.action == "delete_case":
        raw_case_id = _require_positive_int(params.get("case_id"), "case_id")
        case = await db.get(TestCase, raw_case_id)
        if not case:
            raise HTTPException(status_code=404, detail="用例不存在")
        module = await db.get(Module, case.module_id)
        if not module or module.project_id != body.project_id:
            raise HTTPException(status_code=404, detail="用例不属于当前项目")
        case_name = case.name
        local_run_ids = await case_run_ids(db, [raw_case_id]) if settings.ATP_LOCAL_MODE else []
        await db.delete(case)
        await write_audit_log(
            db,
            action="hermes_chat_delete_case",
            resource_type="test_case",
            resource_id=raw_case_id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话删除用例 #{raw_case_id}：{case_name}",
        )
        await db.commit()
        if local_run_ids:
            await asyncio.to_thread(delete_run_artifacts, local_run_ids)
        await invalidate_stats_cache()
        return AiChatExecuteActionOut(
            action="delete_case",
            message=f"已删除测试用例 #{raw_case_id}：{case_name}",
            resource_id=raw_case_id,
            route="/cases",
        )

    if body.action == "delete_defect":
        raw_defect_id = _require_positive_int(params.get("defect_id"), "defect_id")
        defect = await db.get(Defect, raw_defect_id)
        if not defect or defect.project_id != body.project_id:
            raise HTTPException(status_code=404, detail="缺陷不存在或不属于当前项目")
        defect_title = defect.title
        await db.delete(defect)
        await write_audit_log(
            db,
            action="hermes_chat_delete_defect",
            resource_type="defect",
            resource_id=raw_defect_id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话删除缺陷 #{raw_defect_id}：{defect_title}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="delete_defect",
            message=f"已删除缺陷 #{raw_defect_id}：{defect_title}",
            resource_id=raw_defect_id,
            route="/bugs",
        )

    if body.action == "update_knowledge":
        raw_knowledge_id = _require_positive_int(params.get("knowledge_id"), "knowledge_id")
        entry = await db.get(KnowledgeEntry, raw_knowledge_id)
        if not entry or entry.project_id != body.project_id:
            raise HTTPException(status_code=404, detail="知识条目不存在或不属于当前项目")
        updated = False
        if "title" in params and params["title"] is not None:
            if not isinstance(params["title"], str) or not params["title"].strip():
                raise HTTPException(status_code=400, detail="知识标题不能为空")
            entry.title = params["title"].strip()[:256]
            updated = True
        if "content" in params and params["content"] is not None:
            if not isinstance(params["content"], str) or not params["content"].strip():
                raise HTTPException(status_code=400, detail="知识正文不能为空")
            entry.content = params["content"].strip()[:50000]
            updated = True
        if "summary" in params:
            entry.summary = params["summary"].strip()[:1000] or None if isinstance(params["summary"], str) else None
            updated = True
        if "status" in params and params["status"] is not None:
            next_status = str(params["status"]).strip().lower()
            if next_status not in {"draft", "published", "archived"}:
                raise HTTPException(status_code=400, detail="无效的知识状态，仅支持 draft / published / archived")
            entry.status = next_status
            updated = True
        if not updated:
            raise HTTPException(status_code=400, detail="未提供可更新的知识字段")
        entry.version = int(entry.version or 1) + 1
        await write_audit_log(
            db,
            action="hermes_chat_update_knowledge",
            resource_type="knowledge_entry",
            resource_id=entry.id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话更新知识条目 #{entry.id}：{entry.title}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="update_knowledge",
            message=f"已更新知识条目 #{entry.id}：{entry.title}",
            resource_id=entry.id,
            route="/knowledge",
        )

    if body.action == "delete_knowledge":
        raw_knowledge_id = _require_positive_int(params.get("knowledge_id"), "knowledge_id")
        entry = await db.get(KnowledgeEntry, raw_knowledge_id)
        if not entry or entry.project_id != body.project_id:
            raise HTTPException(status_code=404, detail="知识条目不存在或不属于当前项目")
        entry_title = entry.title
        await db.delete(entry)
        await write_audit_log(
            db,
            action="hermes_chat_delete_knowledge",
            resource_type="knowledge_entry",
            resource_id=raw_knowledge_id,
            user_id=user.id,
            username=user.username,
            project_id=body.project_id,
            detail=f"通过 Hermes 对话删除知识条目 #{raw_knowledge_id}：{entry_title}",
        )
        await db.commit()
        return AiChatExecuteActionOut(
            action="delete_knowledge",
            message=f"已删除知识条目 #{raw_knowledge_id}：{entry_title}",
            resource_id=raw_knowledge_id,
            route="/knowledge",
        )

    title = str(params.get("title") or "").strip()[:256]
    content = str(params.get("content") or "").strip()[:50000]
    if not title or not content:
        raise HTTPException(status_code=400, detail="知识标题和内容不能为空")
    source_type = str(params.get("source_type") or params.get("category") or "experience").strip()
    if source_type not in {"standard", "defect", "solution", "runbook", "experience", "requirement", "execution"}:
        source_type = "experience"
    tags = (
        [str(t)[:32] for t in params.get("tags", []) if str(t).strip()]
        if isinstance(params.get("tags"), list)
        else ["Hermes"]
    )
    entry = KnowledgeEntry(
        project_id=body.project_id,
        source_type=source_type,
        title=title,
        summary=str(params.get("summary") or "").strip()[:1000] or None,
        content=content,
        tags=tags,
        status="draft",
        author_id=user.id,
    )
    db.add(entry)
    await db.flush()
    await write_audit_log(
        db,
        action="hermes_chat_create_knowledge",
        resource_type="knowledge_entry",
        resource_id=entry.id,
        user_id=user.id,
        username=user.username,
        project_id=body.project_id,
        detail=f"通过 Hermes 对话创建知识草稿: {entry.title}",
    )
    await db.commit()
    return AiChatExecuteActionOut(
        action="create_knowledge",
        message=f"已保存知识草稿 #{entry.id}：{entry.title}",
        resource_id=entry.id,
        route="/knowledge",
    )
