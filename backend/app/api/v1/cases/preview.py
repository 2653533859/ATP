"""Send one unsaved API request from the case editor without creating a run."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.url_security import validate_public_http_url
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.services.api_auth import build_digest_auth, resolve_oauth2_client_credentials_token
from app.worker.executors.api_executor import _build_request_kwargs

router = APIRouter(tags=["用例管理"])
MAX_PREVIEW_BYTES = 1024 * 1024


class ApiRequestPreviewIn(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
    url: str = Field(min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    body_type: Literal["none", "json", "form", "multipart", "xml", "raw"] = "none"
    body: Any = None
    multipart: list[dict[str, Any]] = Field(default_factory=list)
    auth: dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=30, ge=1, le=60)


class ApiRequestPreviewOut(BaseModel):
    status_code: int
    reason: str
    duration_ms: int
    size_bytes: int
    truncated: bool
    headers: dict[str, str]
    body: str


def _validate_preview_url(value: str) -> str:
    if not settings.ATP_LOCAL_MODE:
        return validate_public_http_url(value)
    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("地址必须是 http 或 https URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("地址不能包含用户名或密码")
    return normalized


def _validate_fields(body: ApiRequestPreviewIn) -> None:
    for fields in (body.headers, body.params, body.cookies):
        if len(fields) > 100 or any(len(key) > 256 or len(value) > 8192 for key, value in fields.items()):
            raise ValueError("请求头、参数或 Cookie 超出预览限制")
    if len(body.multipart) > 50:
        raise ValueError("multipart 字段过多")


@router.post("/projects/{project_id}/api-request-preview", response_model=ApiRequestPreviewOut)
async def preview_api_request(
    project_id: int,
    body: ApiRequestPreviewIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApiRequestPreviewOut:
    """Explicitly send the current editor request once; no case, run or session is saved."""
    await assert_project_access(db, user, project_id, ProjectRole.editor)
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        _validate_fields(body)
        url = await asyncio.to_thread(_validate_preview_url, body.url)
        auth_config = body.auth
        auth_type = str(auth_config.get("type") or "none")
        if auth_type not in {"none", "bearer", "basic", "apikey", "digest", "oauth2_client_credentials"}:
            raise ValueError("不支持的认证方式")
        headers = dict(body.headers)
        request_auth: httpx.Auth | tuple[str, str] | None = None
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
        elif auth_type == "basic":
            request_auth = (
                str(auth_config.get("username", "")),
                str(auth_config.get("password", "")),
            )
        elif auth_type == "apikey":
            header_name = str(auth_config.get("header") or "X-API-Key").strip()
            if not header_name:
                raise ValueError("API Key 请求头不能为空")
            headers[header_name] = str(auth_config.get("value") or "")
        if auth_type == "digest":
            request_auth = build_digest_auth(auth_config, str)
        if auth_type == "oauth2_client_credentials":
            token_url = str(auth_config.get("token_url") or "")
            await asyncio.to_thread(_validate_preview_url, token_url)
            headers["Authorization"] = await resolve_oauth2_client_credentials_token(
                auth_config, str, float(body.timeout), {}
            )

        step = body.model_dump()
        request_kwargs, _ = await _build_request_kwargs(
            step,
            {},
            headers=headers,
            params=body.params,
            cookies=body.cookies,
            project_id=project_id,
        )
        if auth_type in {"basic", "digest"}:
            request_kwargs["auth"] = request_auth
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=body.timeout, follow_redirects=False) as client:
            async with client.stream(body.method, url, **request_kwargs) as response:
                chunks = bytearray()
                truncated = False
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    remaining = MAX_PREVIEW_BYTES - len(chunks)
                    chunks.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        truncated = True
                        break
                duration_ms = int((time.monotonic() - started) * 1000)
                content_type = response.headers.get("content-type", "").lower()
                readable = any(item in content_type for item in ("json", "text", "xml", "javascript", "html"))
                try:
                    content = chunks.decode(response.encoding or "utf-8", errors="replace") if readable else ""
                except LookupError:
                    content = chunks.decode("utf-8", errors="replace")
                if not readable and chunks:
                    content = "[二进制响应，正文未显示]"
                return ApiRequestPreviewOut(
                    status_code=response.status_code,
                    reason=response.reason_phrase,
                    duration_ms=duration_ms,
                    size_bytes=len(chunks),
                    truncated=truncated,
                    headers=dict(response.headers),
                    body=content,
                )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="请求超时") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"请求失败：{type(exc).__name__}") from exc
