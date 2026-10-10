"""Dedicated conversational AI chat with streaming (SSE) support."""

from __future__ import annotations

import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.core.encryption import decrypt
from app.models.ai_llm_config import AILLMConfig
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.services.ai_case.llm_client import LLMRequest, stream_llm
from app.services.ai_governance import check_and_incr_daily_limit, llm_extra_params

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


@router.post("/stream")
async def chat_stream(
    body: AiChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """流式返回 AI 自由对话内容 (SSE)"""
    if body.project_id is not None:
        await assert_project_access(db, user, body.project_id, ProjectRole.viewer)
    config, api_key = await _resolve_active_llm(db, body.project_id)

    async def event_generator():
        if not config:
            fallback = (
                "当前平台尚未配置可用的大语言模型。请管理员前往「系统设置 ➔ AI 模型配置」"
                "添加并启用模型（支持通义千问、DeepSeek、OpenAI 或本地 Ollama），即可开启自然闲聊。"
            )
            yield f"data: {json.dumps({'token': fallback}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not await check_and_incr_daily_limit(config=config, capability="ai_chat"):
            yield f"data: {json.dumps({'error': '已达模型每日调用上限，请明日重试或联系管理员提升配额'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        history_lines = []
        for item in body.history[-10:]:
            prefix = "用户" if item.role == "user" else "助手"
            history_lines.append(f"{prefix}: {item.content}")
        history_block = "\n".join(history_lines)

        user_prompt = f"历史对话：\n{history_block}\n\n当前用户问题：{body.query}" if history_block else body.query

        request = LLMRequest(
            provider=config.provider,
            api_key=api_key,
            model_name=config.model_name,
            prompt=user_prompt,
            endpoint=config.endpoint,
            system_prompt=_CHAT_SYSTEM_PROMPT,
            timeout_seconds=90.0,
            extra_params=llm_extra_params(config),
        )

        try:
            async for token in stream_llm(request):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
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
