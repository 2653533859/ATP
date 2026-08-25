"""AI LLM 配置管理：仅管理员可访问。

api_key 在保存时 Fernet 加密，返回时仅暴露 ``has_api_key`` 标记。
"""

from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.core.encryption import decrypt, encrypt
from app.models.ai_llm_config import AILLMConfig
from app.models.user import User
from app.schemas.ai_llm_config import (
    AILLMConnectionTestIn,
    AILLMConnectionTestOut,
    AILLMConfigCreateIn,
    AILLMModelDiscoveryIn,
    AILLMModelDiscoveryOut,
    AILLMConfigOut,
    AILLMConfigUpdateIn,
)
from app.services.ai_case.model_discovery import discover_models, resolve_endpoint
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_governance import llm_extra_params, llm_extra_params_from_values
from app.services.audit import write_audit_log

router = APIRouter(prefix="/ai/llm-configs", tags=["AI 配置"])


def _to_out(config: AILLMConfig) -> AILLMConfigOut:
    return AILLMConfigOut(
        id=config.id,
        name=config.name,
        provider=config.provider,  # type: ignore[arg-type]
        endpoint=config.endpoint,
        model_name=config.model_name,
        default_params=dict(config.default_params or {}),
        enabled=config.enabled,
        supports_vision=config.supports_vision,
        description=config.description,
        has_api_key=bool(config.api_key_encrypted),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("", response_model=list[AILLMConfigOut])
async def list_llm_configs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(AILLMConfig).order_by(AILLMConfig.id.desc()))
    return [_to_out(c) for c in result.scalars().all()]


@router.post("/models", response_model=AILLMModelDiscoveryOut)
async def discover_llm_models(
    body: AILLMModelDiscoveryIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = None
    if body.config_id is not None:
        config = await db.get(AILLMConfig, body.config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")

    same_provider = config is not None and config.provider == body.provider
    endpoint = body.endpoint if body.endpoint is not None else config.endpoint if same_provider else None
    api_key = (body.api_key or "").strip()
    if not api_key and same_provider and config is not None and config.api_key_encrypted:
        try:
            api_key = decrypt(config.api_key_encrypted)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="现有 API Key 解密失败，请重新输入") from exc
    if body.provider != "ollama" and not api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")

    try:
        models = await discover_models(body.provider, endpoint, api_key)
        resolved = resolve_endpoint(body.provider, endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        provider_status = exc.response.status_code
        if provider_status in {401, 403}:
            detail = "供应商模型列表鉴权失败，请填写该供应商签发的 API Token；Ollama 原生接口通常不需要 API Key"
        elif provider_status == 405:
            detail = "供应商不支持当前模型列表请求方式，请检查 Endpoint；Ollama 原生请使用 11434，Open WebUI 请使用 OpenAI 兼容协议和 /v1"
        else:
            detail = f"供应商模型列表请求失败（HTTP {provider_status}）"
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="供应商模型列表请求超时") from exc
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="无法连接供应商模型接口") from None

    return AILLMModelDiscoveryOut(provider=body.provider, endpoint=resolved, models=models)


@router.post("/test-connection", response_model=AILLMConnectionTestOut)
async def test_llm_connection(
    body: AILLMConnectionTestIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Run a bounded text request without returning provider output or secrets."""
    config = None
    if body.config_id is not None:
        config = await db.get(AILLMConfig, body.config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")

    provider = body.provider or (config.provider if config else None)
    if not provider:
        raise HTTPException(status_code=400, detail="请先选择供应商")
    model_name = (body.model_name or (config.model_name if config else "")).strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="请先填写模型名称")

    same_provider = config is not None and config.provider == provider
    endpoint = body.endpoint if body.endpoint is not None else config.endpoint if same_provider else None
    api_key = (body.api_key or "").strip()
    if not api_key and same_provider and config is not None and config.api_key_encrypted:
        try:
            api_key = decrypt(config.api_key_encrypted)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="现有 API Key 解密失败，请重新输入") from exc
    if provider != "ollama" and not api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")

    try:
        resolved_endpoint = resolve_endpoint(provider, endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    extra_params = (
        llm_extra_params(config) if body.default_params is None else llm_extra_params_from_values(body.default_params)
    )
    if extra_params:
        extra_params.pop("temperature", None)
        extra_params.pop("max_tokens", None)

    started = time.perf_counter()
    try:
        await call_llm(
            LLMRequest(
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                prompt="Reply with OK only.",
                endpoint=resolved_endpoint,
                temperature=0.0,
                max_tokens=4,
                timeout_seconds=15.0,
                extra_params=extra_params,
            )
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            detail = "供应商鉴权失败，请检查 API Key"
        elif exc.response.status_code == 404:
            detail = "模型或接口不存在，请检查 Endpoint 和模型名称"
        else:
            detail = f"供应商请求失败（HTTP {exc.response.status_code}）"
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="模型连接测试超时") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="无法连接供应商模型接口") from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="供应商返回格式无法识别") from exc

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    await write_audit_log(
        db,
        action="ai_llm_config_test",
        resource_type="ai_llm_config",
        resource_id=getattr(config, "id", None),
        user_id=getattr(_, "id", None),
        username=getattr(_, "username", ""),
        detail=f"测试 AI LLM 连接: {provider}/{model_name}, latency_ms={latency_ms}",
    )
    await db.commit()
    return AILLMConnectionTestOut(
        provider=provider,
        model_name=model_name,
        latency_ms=latency_ms,
        response_received=True,
        message="连接成功",
    )


@router.post("", response_model=AILLMConfigOut, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    body: AILLMConfigCreateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = AILLMConfig(
        name=body.name,
        provider=body.provider,
        api_key_encrypted=encrypt(body.api_key) if body.api_key else "",
        endpoint=body.endpoint,
        model_name=body.model_name,
        default_params=body.default_params or {},
        enabled=body.enabled,
        supports_vision=body.supports_vision,
        description=body.description,
    )
    db.add(config)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="名称已存在")
    await db.refresh(config)
    await write_audit_log(
        db,
        action="ai_llm_config_create",
        resource_type="ai_llm_config",
        resource_id=config.id,
        user_id=getattr(_, "id", None),
        username=getattr(_, "username", ""),
        detail=f"创建 AI LLM 配置: {config.name} ({config.provider}/{config.model_name})",
    )
    await db.commit()
    return _to_out(config)


@router.get("/{config_id}", response_model=AILLMConfigOut)
async def get_llm_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = await db.get(AILLMConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return _to_out(config)


@router.patch("/{config_id}", response_model=AILLMConfigOut)
async def update_llm_config(
    config_id: int,
    body: AILLMConfigUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = await db.get(AILLMConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    payload = body.model_dump(exclude_none=True)
    requested_provider = payload.get("provider", config.provider)
    if requested_provider != "ollama" and "api_key" not in payload and not config.api_key_encrypted:
        raise HTTPException(status_code=400, detail="该供应商必须填写 API Key")
    requested_endpoint = payload.get("endpoint", config.endpoint)
    if requested_provider == "openai_compatible" and not str(requested_endpoint or "").strip():
        raise HTTPException(status_code=400, detail="OpenAI 兼容供应商必须填写 Endpoint")
    if "api_key" in payload:
        config.api_key_encrypted = encrypt(payload.pop("api_key"))
    for key, value in payload.items():
        setattr(config, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="名称已存在")
    await db.refresh(config)
    await write_audit_log(
        db,
        action="ai_llm_config_update",
        resource_type="ai_llm_config",
        resource_id=config.id,
        user_id=getattr(_, "id", None),
        username=getattr(_, "username", ""),
        detail=f"更新 AI LLM 配置: {config.name}",
    )
    await db.commit()
    return _to_out(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = await db.get(AILLMConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    config_name = config.name
    await db.delete(config)
    await write_audit_log(
        db,
        action="ai_llm_config_delete",
        resource_type="ai_llm_config",
        resource_id=config_id,
        user_id=getattr(_, "id", None),
        username=getattr(_, "username", ""),
        detail=f"删除 AI LLM 配置: {config_name}",
    )
    await db.commit()
