"""Isolated API Scenario Debug Sessions with Chained Fingerprints, Offline Assertion Recheck,
UNCHECKED Semantics, and 3-Tier Precheck (save / debug / run).
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.url_security import validate_http_url_syntax, validate_public_http_url
from app.services.api_auth import build_digest_auth, resolve_oauth2_client_credentials_token
from app.services.api_hooks import execute_api_hooks
from app.services.api_session import apply_cookies, serialize_cookies
from app.services.execution_contract import assertion_result, extraction_result, response_contract
from app.services.template_variables import render_template_string
from app.worker.executors._assertion_helpers import build_basic_auth_header
from app.worker.executors.api_executor import (
    _assert,
    _build_request_kwargs,
    _extract_value,
    _parse_response_body,
    _render_assertion,
    _resolve_schema_assertions,
    _send_request_with_write_safe_retry,
    parse_api_retry_count,
)

logger = logging.getLogger(__name__)

DEBUG_SESSION_TTL_SECONDS = 1800.0
MAX_DEBUG_SESSIONS_PER_USER = 20
MAX_DEBUG_RESPONSE_BYTES = 5 * 1024 * 1024

_VAR_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.-]*)\s*\}\}")
_PATH_PARAM_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")

PrecheckMode = Literal["save", "debug", "run"]
DebugExecuteMode = Literal["single", "through", "collect"]


class ApiDebugSessionError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class _CachedResponse:
    """Minimal httpx.Response-compatible wrapper for offline assertion recheck."""

    status_code: int
    headers: httpx.Headers


@dataclass
class ApiDebugSession:
    session_id: str
    user_id: int
    project_id: int
    editor_id: str
    env_id: int | None
    touched: float = field(default_factory=time.monotonic)
    fingerprints: dict[str, str] = field(default_factory=dict)
    assertion_fingerprints: dict[str, str] = field(default_factory=dict)
    responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    context_after: dict[str, dict[str, Any]] = field(default_factory=dict)
    cookies_after: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    collect: bool = False
    status: str = "idle"
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_SESSIONS_LOCK = threading.RLock()
_SESSIONS: dict[str, ApiDebugSession] = {}


def _step_uid(step: dict[str, Any], index: int) -> str:
    raw = str(step.get("uid") or step.get("id") or "").strip()
    return raw or f"step_{index + 1}"


def _request_canonical_payload(step: dict[str, Any]) -> dict[str, Any]:
    """Canonical request-only fields; changing name/description/assertions does NOT alter this hash."""
    return {
        "method": str(step.get("method") or "GET").upper(),
        "url": str(step.get("url") or ""),
        "headers": step.get("headers") or {},
        "params": step.get("params") or {},
        "cookies": step.get("cookies") or {},
        "body_type": step.get("body_type") or "none",
        "body": step.get("body"),
        "auth": step.get("auth") or {},
        "pre_actions": step.get("pre_actions") or [],
        "extractions": step.get("extractions") or [],
        "timeout": step.get("timeout", 30),
        "retry_count": parse_api_retry_count(step),
    }


def _assertions_fingerprint(step: dict[str, Any]) -> str:
    payload = json.dumps(step.get("assertions") or [], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_chained_fingerprints(steps: list[dict[str, Any]], env_vars: dict[str, Any]) -> dict[str, str]:
    chain = json.dumps(env_vars or {}, sort_keys=True, ensure_ascii=False, default=str)
    result: dict[str, str] = {}
    for idx, step in enumerate(steps):
        uid = _step_uid(step, idx)
        req_json = json.dumps([uid, _request_canonical_payload(step)], sort_keys=True, ensure_ascii=False, default=str)
        chain = hashlib.sha256((chain + req_json).encode("utf-8")).hexdigest()
        result[uid] = chain
    return result


def _sync_session_fingerprints(session: ApiDebugSession, steps: list[dict[str, Any]], env_vars: dict[str, Any]) -> None:
    """Invalidate changed step & downstream caches; preserve responses when only assertions changed."""
    new_fps = _compute_chained_fingerprints(steps, env_vars)
    stale_uids = {uid for uid, old_fp in session.fingerprints.items() if new_fps.get(uid) != old_fp}
    for uid in stale_uids:
        for mapping in (
            session.responses,
            session.context_after,
            session.cookies_after,
            session.results,
            session.assertion_fingerprints,
        ):
            mapping.pop(uid, None)
    session.fingerprints = new_fps

    for idx, step in enumerate(steps):
        uid = _step_uid(step, idx)
        res = session.results.get(uid)
        if not res:
            continue
        res["name"] = str(step.get("name") or f"Step {idx + 1}")
        current_afp = _assertions_fingerprint(step)
        if uid in session.responses and session.assertion_fingerprints.get(uid) != current_afp:
            res["assertions_pending"] = True
        elif res.get("assertions_pending") and session.assertion_fingerprints.get(uid) == current_afp:
            res["assertions_pending"] = False


def reap_expired_debug_sessions() -> int:
    now = time.monotonic()
    removed = 0
    with _SESSIONS_LOCK:
        for sid, sess in list(_SESSIONS.items()):
            if (now - sess.touched) > DEBUG_SESSION_TTL_SECONDS and sess.status != "running":
                _SESSIONS.pop(sid, None)
                removed += 1
    return removed


def create_api_debug_session(
    *,
    user_id: int,
    project_id: int,
    editor_id: str,
    env_id: int | None,
) -> ApiDebugSession:
    reap_expired_debug_sessions()
    with _SESSIONS_LOCK:
        owned = sum(1 for item in _SESSIONS.values() if item.user_id == user_id)
        if owned >= MAX_DEBUG_SESSIONS_PER_USER:
            raise ApiDebugSessionError("当前用户的活跃调试会话过多，请关闭不再使用的调试页面", status_code=429)
        sid = f"adbg_{uuid.uuid4().hex[:12]}"
        sess = ApiDebugSession(
            session_id=sid,
            user_id=user_id,
            project_id=project_id,
            editor_id=editor_id.strip() or "default",
            env_id=env_id,
        )
        _SESSIONS[sid] = sess
        return sess


def get_api_debug_session(session_id: str, *, user_id: int, is_admin: bool = False) -> ApiDebugSession:
    reap_expired_debug_sessions()
    with _SESSIONS_LOCK:
        sess = _SESSIONS.get(session_id)
        if sess is None:
            raise ApiDebugSessionError(f"调试会话不存在或已过期: {session_id}", status_code=404)
        if not is_admin and sess.user_id != user_id:
            raise ApiDebugSessionError("无权访问其他用户的调试会话", status_code=403)
        sess.touched = time.monotonic()
        return sess


def delete_api_debug_session(session_id: str, *, user_id: int, is_admin: bool = False) -> bool:
    with _SESSIONS_LOCK:
        sess = _SESSIONS.get(session_id)
        if sess is None:
            return False
        if not is_admin and sess.user_id != user_id:
            raise ApiDebugSessionError("无权释放其他用户的调试会话", status_code=403)
        _SESSIONS.pop(session_id, None)
        return True


def _collect_var_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(value, str):
        for token in _VAR_TOKEN_RE.findall(value):
            if not token.startswith("$"):
                tokens.add(token)
    elif isinstance(value, dict):
        for child in value.values():
            tokens.update(_collect_var_tokens(child))
    elif isinstance(value, list):
        for child in value:
            tokens.update(_collect_var_tokens(child))
    return tokens


def precheck_api_scenario_steps(
    steps: list[dict[str, Any]],
    *,
    env_vars: dict[str, Any] | None = None,
    mode: PrecheckMode = "run",
    target_step_uid: str | None = None,
) -> list[dict[str, Any]]:
    """Three-tier precheck:
    - save: structural integrity, unique step uids, valid dependency ordering (allows drafts & 0 assertions)
    - debug: validates up to target_step_uid (URL, auth required fields, env/upstream variables)
    - run: full validation + requires >=1 request step + >=1 assertion per step
    """
    issues: list[dict[str, Any]] = []
    if mode == "run" and not steps:
        issues.append(
            {
                "step_uid": None,
                "step_index": None,
                "step_name": "",
                "section": "steps",
                "field": "steps",
                "message": "正式运行的场景至少需要一个接口请求步骤",
            }
        )
        return issues

    seen_uids: set[str] = set()
    available_vars: set[str] = {"trace_id", "timestamp", "NOW", *(str(k) for k in (env_vars or {}).keys())}
    target_index = len(steps) - 1
    if mode == "debug" and target_step_uid:
        for idx, step in enumerate(steps):
            if _step_uid(step, idx) == target_step_uid:
                target_index = idx
                break

    for idx, step in enumerate(steps):
        uid = _step_uid(step, idx)
        step_name = str(step.get("name") or f"Step {idx + 1}")
        if uid in seen_uids:
            issues.append(
                {
                    "step_uid": uid,
                    "step_index": idx,
                    "step_name": step_name,
                    "section": "params",
                    "field": "uid",
                    "message": f"步骤标识重复: {uid}",
                }
            )
        seen_uids.add(uid)

        deps = step.get("depends_on") or []
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, int) and (dep < 0 or dep >= idx):
                    issues.append(
                        {
                            "step_uid": uid,
                            "step_index": idx,
                            "step_name": step_name,
                            "section": "params",
                            "field": "depends_on",
                            "message": f"步骤只能依赖前序步骤，非法依赖索引: {dep}",
                        }
                    )

        if mode in {"debug", "run"} and idx <= target_index:
            raw_url = str(step.get("url") or "").strip()
            if not raw_url:
                issues.append(
                    {
                        "step_uid": uid,
                        "step_index": idx,
                        "step_name": step_name,
                        "section": "params",
                        "field": "url",
                        "message": "请求 URL 不能为空",
                    }
                )
            else:
                rendered_url = render_template_string(raw_url, {k: str(v) for k, v in (env_vars or {}).items()})
                unresolved_path_params = _PATH_PARAM_RE.findall(rendered_url)
                if unresolved_path_params:
                    issues.append(
                        {
                            "step_uid": uid,
                            "step_index": idx,
                            "step_name": step_name,
                            "section": "params",
                            "field": "url",
                            "message": f"URL 存在未替换的路径参数: {', '.join(unresolved_path_params)}",
                        }
                    )
                if "{{" not in rendered_url:
                    try:
                        parsed = httpx.URL(rendered_url)
                        if parsed.scheme not in {"http", "https"} or not parsed.host:
                            issues.append(
                                {
                                    "step_uid": uid,
                                    "step_index": idx,
                                    "step_name": step_name,
                                    "section": "params",
                                    "field": "url",
                                    "message": "请输入完整的 HTTP/HTTPS 请求地址（或配置环境变量 base_url）",
                                }
                            )
                    except httpx.InvalidURL:
                        issues.append(
                            {
                                "step_uid": uid,
                                "step_index": idx,
                                "step_name": step_name,
                                "section": "params",
                                "field": "url",
                                "message": "请求 URL 格式无效",
                            }
                        )

            # Auth required field checks
            auth_cfg = step.get("auth") or {}
            if isinstance(auth_cfg, dict):
                auth_type = str(auth_cfg.get("type") or "none").lower()
                if auth_type == "bearer" and not str(auth_cfg.get("token") or "").strip():
                    issues.append(
                        {
                            "step_uid": uid,
                            "step_index": idx,
                            "step_name": step_name,
                            "section": "auth",
                            "field": "auth.token",
                            "message": "Bearer 认证令牌不能为空",
                        }
                    )
                elif auth_type == "basic" and not str(auth_cfg.get("username") or "").strip():
                    issues.append(
                        {
                            "step_uid": uid,
                            "step_index": idx,
                            "step_name": step_name,
                            "section": "auth",
                            "field": "auth.username",
                            "message": "Basic 认证用户名不能为空",
                        }
                    )
                elif auth_type == "apikey" and not str(auth_cfg.get("value") or "").strip():
                    issues.append(
                        {
                            "step_uid": uid,
                            "step_index": idx,
                            "step_name": step_name,
                            "section": "auth",
                            "field": "auth.value",
                            "message": "API Key 凭证值不能为空",
                        }
                    )

            # Check variable reachability against env + upstream extractions
            if env_vars is not None:
                section_map = [
                    ("params", "url", step.get("url")),
                    ("headers", "headers", step.get("headers")),
                    ("params", "params", step.get("params")),
                    ("body", "body", step.get("body")),
                    ("auth", "auth", step.get("auth")),
                ]
                for section, field_name, val in section_map:
                    for token in sorted(_collect_var_tokens(val)):
                        if token not in available_vars:
                            issues.append(
                                {
                                    "step_uid": uid,
                                    "step_index": idx,
                                    "step_name": step_name,
                                    "section": section,
                                    "field": field_name,
                                    "message": f"引用的变量 {{{{{token}}}}} 在环境变量和前序步骤提取中均未定义",
                                }
                            )

        if mode == "run":
            assertions = step.get("assertions") or []
            if not isinstance(assertions, list) or len(assertions) == 0:
                issues.append(
                    {
                        "step_uid": uid,
                        "step_index": idx,
                        "step_name": step_name,
                        "section": "assertions",
                        "field": "assertions",
                        "message": "正式运行前，每个接口步骤至少需要配置一条断言",
                    }
                )

        # Register variables produced by this step for downstream reachability
        for ex in step.get("extractions") or []:
            if isinstance(ex, dict):
                var_name = str(ex.get("variable") or ex.get("name") or "").strip()
                if var_name:
                    available_vars.add(var_name)

    return issues


async def _evaluate_step_assertions(
    db: AsyncSession,
    project_id: int | None,
    assertions_cfg: list[dict[str, Any]],
    cached_resp: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], str | None]:
    assertions = await _resolve_schema_assertions(db, assertions_cfg, project_id)
    if not assertions:
        return "unchecked", [], "尚未配置断言，当前结果仅表示收到响应（UNCHECKED）"

    fake_resp = _CachedResponse(
        status_code=int(cached_resp.get("status_code") or 0),
        headers=httpx.Headers(cached_resp.get("headers") or {}),
    )
    body = cached_resp.get("body")
    duration_ms = int(cached_resp.get("duration_ms") or 0)

    records: list[dict[str, Any]] = []
    error_msg: str | None = None
    status = "passed"
    for assertion in assertions:
        rendered = _render_assertion(assertion, context)
        passed, msg = _assert(rendered, fake_resp, body, duration_ms)  # type: ignore[arg-type]
        records.append(assertion_result(rendered, passed=passed, message=msg))
        if not passed and status == "passed":
            status = "failed"
            error_msg = msg
    return status, records, error_msg


async def _execute_one_debug_step(
    step: dict[str, Any],
    *,
    uid: str,
    step_index: int,
    client: httpx.AsyncClient,
    context: dict[str, Any],
    db: AsyncSession,
    project_id: int | None,
    enforce_ssrf: bool = True,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    step_start = time.monotonic()
    step_name = str(step.get("name") or f"Step {step_index + 1}")
    request_data: dict[str, Any] = {}
    cached_response: dict[str, Any] | None = None
    assertion_records: list[dict[str, Any]] = []
    extraction_records: list[dict[str, Any]] = []
    retry_meta: dict[str, Any] = {
        "attempts": 1,
        "retry_count": parse_api_retry_count(step),
        "retried": False,
        "history": [],
    }
    error_msg: str | None = None
    status = "passed"
    oauth_token_cache: dict[str, tuple[str, float]] = {}

    try:
        execute_api_hooks(step.get("pre_actions"), context)
        raw_url = render_template_string(str(step.get("url") or ""), context)
        if enforce_ssrf and not settings.ATP_LOCAL_MODE:
            url = await asyncio.to_thread(validate_public_http_url, raw_url)
        else:
            url = validate_http_url_syntax(raw_url)
        method = str(step.get("method") or "GET").upper()
        headers = {str(k): render_template_string(str(v), context) for k, v in (step.get("headers") or {}).items()}
        params = {str(k): render_template_string(str(v), context) for k, v in (step.get("params") or {}).items()}
        cookies = {str(k): render_template_string(str(v), context) for k, v in (step.get("cookies") or {}).items()}
        timeout = float(step.get("timeout", 30))

        auth_cfg = step.get("auth") or {}
        auth_type = str(auth_cfg.get("type") or "")
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {render_template_string(str(auth_cfg.get('token') or ''), context)}"
        elif auth_type == "basic":
            headers["Authorization"] = build_basic_auth_header(
                auth_cfg, lambda value: render_template_string(str(value), context)
            )
        elif auth_type == "apikey":
            header_name = render_template_string(str(auth_cfg.get("header") or "X-API-Key"), context).strip()
            header_value = render_template_string(str(auth_cfg.get("value") or ""), context)
            if header_name:
                headers[header_name] = header_value

        request_kwargs, record_body = await _build_request_kwargs(
            step,
            context,
            headers=headers,
            params=params,
            cookies=cookies,
            project_id=project_id,
        )
        if auth_type == "digest":
            request_kwargs["auth"] = build_digest_auth(
                auth_cfg, lambda value: render_template_string(str(value), context)
            )
        elif auth_type == "oauth2_client_credentials":
            headers["Authorization"] = await resolve_oauth2_client_credentials_token(
                auth_cfg,
                lambda value: render_template_string(str(value), context),
                timeout,
                oauth_token_cache,
            )

        request_data = {
            "method": method,
            "url": url,
            "headers": headers,
            "params": params,
            "cookies": cookies,
            "body": record_body,
        }
        if cookies:
            client.cookies.update(cookies)
            request_kwargs.pop("cookies", None)

        resp, streamed_body, retry_meta = await _send_request_with_write_safe_retry(
            client,
            method,
            url,
            timeout,
            request_kwargs,
            step.get("response_type"),
            int(step.get("sse_max_events", 100)),
            retry_count=parse_api_retry_count(step),
        )
        if streamed_body is None and len(resp.content) > MAX_DEBUG_RESPONSE_BYTES:
            raise ValueError(f"调试响应体超过 {MAX_DEBUG_RESPONSE_BYTES // (1024 * 1024)} MiB 上限，已中止解析")
        duration_ms = int((time.monotonic() - step_start) * 1000)
        resp_body = (
            streamed_body if streamed_body is not None else _parse_response_body(resp, step.get("response_type"))
        )
        cached_response = response_contract(
            "http",
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=resp_body,
            duration_ms=duration_ms,
        )
        cached_response["cookies"] = {c.name: c.value for c in resp.cookies.jar}
        cached_response["retry"] = retry_meta

        for extraction in step.get("extractions") or []:
            if not isinstance(extraction, dict) or not extraction.get("variable"):
                continue
            val = _extract_value(
                resp_body,
                extraction.get("expression", ""),
                extraction.get("type", "jsonpath"),
                response_headers=dict(resp.headers),
            )
            if val is not None:
                context[extraction["variable"]] = val
            extraction_records.append(
                extraction_result(
                    extraction,
                    value=val,
                    success=val is not None,
                    error=None if val is not None else "未提取到值",
                )
            )
        cached_response["extractions"] = extraction_records

        execute_api_hooks(
            step.get("post_actions"),
            context,
            response_body=resp_body,
            response_headers=dict(resp.headers),
        )

        status, assertion_records, error_msg = await _evaluate_step_assertions(
            db,
            project_id,
            step.get("assertions") or [],
            cached_response,
            context,
        )
        cached_response["assertions"] = assertion_records
        cached_response["verification_status"] = "unchecked" if status == "unchecked" else "verified"
    except Exception as exc:  # noqa: BLE001
        status = "error"
        error_msg = str(exc)

    duration_ms = int((time.monotonic() - step_start) * 1000)
    step_result = {
        "step_uid": uid,
        "step_index": step_index,
        "name": step_name,
        "status": status,
        "assertions_pending": False,
        "duration_ms": duration_ms,
        "request": request_data,
        "response": cached_response,
        "assertions": assertion_records,
        "extractions": extraction_records,
        "retry": retry_meta,
        "error": error_msg,
    }
    return step_result, cached_response


async def execute_api_debug_session(
    session: ApiDebugSession,
    *,
    steps: list[dict[str, Any]],
    target_step_uid: str | None,
    mode: DebugExecuteMode,
    env_vars: dict[str, Any],
    db: AsyncSession,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    async with session._lock:
        if not steps:
            raise ApiDebugSessionError("调试步骤不能为空", status_code=422)
        if target_step_uid:
            target_idx = next((i for i, s in enumerate(steps) if _step_uid(s, i) == target_step_uid), None)
            if target_idx is None:
                raise ApiDebugSessionError(f"调试步骤不存在: {target_step_uid}", status_code=422)
        else:
            target_idx = len(steps) - 1
            target_step_uid = _step_uid(steps[target_idx], target_idx)

        issues = precheck_api_scenario_steps(steps, env_vars=env_vars, mode="debug", target_step_uid=target_step_uid)
        if issues:
            raise ApiDebugSessionError(issues[0]["message"], status_code=422)

        _sync_session_fingerprints(session, steps, env_vars)

        if mode == "single":
            for prev_idx in range(target_idx):
                prev_uid = _step_uid(steps[prev_idx], prev_idx)
                prev_res = session.results.get(prev_uid)
                if prev_res and (prev_res.get("assertions_pending") or prev_res.get("status") != "passed"):
                    prev_name = str(steps[prev_idx].get("name") or f"Step {prev_idx + 1}")
                    raise ApiDebugSessionError(
                        f"请先通过或重新校验前序步骤「{prev_name}」（当前状态: {prev_res.get('status')}）",
                        status_code=409,
                    )

        session.collect = mode == "collect"
        session.status = "running"
        session.touched = time.monotonic()

        start_idx = target_idx if mode == "single" else 0
        # Invalidate target and downstream results before executing
        for i in range(start_idx, len(steps)):
            uid = _step_uid(steps[i], i)
            for mapping in (
                session.responses,
                session.context_after,
                session.cookies_after,
                session.results,
                session.assertion_fingerprints,
            ):
                mapping.pop(uid, None)

        # Restore context & cookies from immediate predecessor when in single mode
        context: dict[str, Any] = copy.deepcopy(env_vars or {})
        restored_cookies: list[dict[str, Any]] = []
        if mode == "single" and target_idx > 0:
            prev_uid = _step_uid(steps[target_idx - 1], target_idx - 1)
            if prev_uid in session.context_after:
                context = copy.deepcopy(session.context_after[prev_uid])
            if prev_uid in session.cookies_after:
                restored_cookies = list(session.cookies_after[prev_uid])

        owns_client = http_client is None
        client = http_client or httpx.AsyncClient(follow_redirects=False)
        if restored_cookies:
            apply_cookies(client.cookies, restored_cookies)

        executed_results: list[dict[str, Any]] = []
        try:
            for idx in range(start_idx, target_idx + 1):
                step = steps[idx]
                uid = _step_uid(step, idx)
                step_res, cached_resp = await _execute_one_debug_step(
                    step,
                    uid=uid,
                    step_index=idx,
                    client=client,
                    context=context,
                    db=db,
                    project_id=session.project_id,
                    enforce_ssrf=owns_client,
                )
                session.results[uid] = step_res
                if cached_resp is not None:
                    session.responses[uid] = cached_resp
                    session.assertion_fingerprints[uid] = _assertions_fingerprint(step)
                    session.context_after[uid] = copy.deepcopy(context)
                    session.cookies_after[uid] = serialize_cookies(client.cookies)
                executed_results.append(step_res)

                if mode == "collect":
                    if step_res["status"] == "error":
                        break
                else:
                    if step_res["status"] != "passed":
                        break
        finally:
            if owns_client:
                await client.aclose()
            session.status = "idle"
            session.touched = time.monotonic()

        return {
            "session_id": session.session_id,
            "mode": mode,
            "executed": executed_results,
            "results": session.results,
            "context": context,
        }


async def recheck_api_debug_assertions(
    session: ApiDebugSession,
    *,
    steps: list[dict[str, Any]],
    target_step_uid: str,
    env_vars: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    """Re-evaluate modified assertions against the cached real response WITHOUT sending any HTTP request."""
    async with session._lock:
        target_idx = next((i for i, s in enumerate(steps) if _step_uid(s, i) == target_step_uid), None)
        if target_idx is None:
            raise ApiDebugSessionError(f"调试步骤不存在: {target_step_uid}", status_code=422)

        _sync_session_fingerprints(session, steps, env_vars)

        if target_step_uid not in session.responses:
            raise ApiDebugSessionError("没有与当前请求配置和环境匹配的真实响应缓存，请先发送调试请求", status_code=409)

        step = steps[target_idx]
        cached_resp = session.responses[target_step_uid]
        context = copy.deepcopy(session.context_after.get(target_step_uid) or env_vars or {})
        status, records, error_msg = await _evaluate_step_assertions(
            db,
            session.project_id,
            step.get("assertions") or [],
            cached_resp,
            context,
        )
        cached_resp["assertions"] = records
        cached_resp["verification_status"] = "unchecked" if status == "unchecked" else "verified"

        existing = session.results.get(target_step_uid) or {
            "step_uid": target_step_uid,
            "step_index": target_idx,
            "name": str(step.get("name") or f"Step {target_idx + 1}"),
            "duration_ms": int(cached_resp.get("duration_ms") or 0),
        }
        existing["status"] = status
        existing["assertions"] = records
        existing["assertions_pending"] = False
        existing["error"] = error_msg
        existing["response"] = cached_resp
        session.results[target_step_uid] = existing
        session.assertion_fingerprints[target_step_uid] = _assertions_fingerprint(step)
        session.touched = time.monotonic()

        return {
            "session_id": session.session_id,
            "step_result": existing,
            "rechecked_offline": True,
        }
