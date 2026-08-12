"""HTTP/REST 接口测试执行器"""

import asyncio
import json
import time
from defusedxml import ElementTree as ET

import httpx
from jsonpath_ng import parse as jp_parse
from opentelemetry.trace import Status, StatusCode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.otel import get_tracer
from app.core.minio_client import read_bytes
from app.models.case import TestRun, TestCase, StepResult, RunStatus
from app.models.api_schema import ApiSchemaAsset
from app.models.project import Module
from app.core.redis_client import publish_run_event
from app.services.ai_healing import apply_healing_hook, enqueue_diagnosis, maybe_enqueue_run_healing
from app.services.api_session import (
    apply_cookies,
    load_project_api_session,
    save_project_api_session,
    serialize_cookies,
)
from app.services.api_hooks import execute_api_hooks
from app.services.api_auth import build_digest_auth, resolve_oauth2_client_credentials_token
from app.services.api_scenario import ApiScenarioError, build_api_scenario_policy, step_dependencies
from app.services.dataset_execution import redact_execution_evidence
from app.services.safe_expressions import SafeExpressionError, evaluate_safe_expression
from app.services.execution_contract import assertion_result, extraction_result, response_contract

_tracer = get_tracer("atp.executor.api")


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        # 实时通知是 best-effort，不影响执行结果落库
        return


async def _resolve_case_project_id(db: AsyncSession, case: TestCase) -> int | None:
    project_id = getattr(case, "project_id", None)
    if isinstance(project_id, int):
        return project_id
    module_id = getattr(case, "module_id", None)
    if not isinstance(module_id, int):
        return None
    result = await db.execute(select(Module.project_id).where(Module.id == module_id))
    return result.scalar_one_or_none()


async def _resolve_schema_assertions(
    db: AsyncSession,
    assertions: object,
    project_id: int | None,
) -> list[dict]:
    """Resolve optional schema asset references without trusting cross-project IDs."""
    if not isinstance(assertions, list):
        return []
    resolved: list[dict] = []
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        item = dict(assertion)
        asset_id = item.get("schema_asset_id")
        if asset_id is not None:
            if project_id is None:
                raise ValueError("JSON Schema 资产缺少项目上下文")
            try:
                normalized_id = int(asset_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("JSON Schema 资产 ID 无效") from exc
            asset = await db.get(ApiSchemaAsset, normalized_id)
            if asset is None or asset.project_id != project_id:
                raise ValueError("JSON Schema 资产不存在或不属于当前项目")
            item["schema"] = asset.definition
        resolved.append(item)
    return resolved


async def _record_skipped_scenario_step(
    db: AsyncSession,
    run: TestRun,
    index: int,
    name: str,
    reason: str,
) -> None:
    result = StepResult(
        run_id=run.id,
        step_index=index,
        name=name,
        status=RunStatus.skipped,
        duration_ms=0,
        response_data={"orchestration": {"skipped": True, "reason": reason}},
        error_message=reason,
    )
    db.add(result)
    await db.commit()
    await _safe_publish_run_event(
        run.id,
        {
            "type": "step_result",
            "run_id": run.id,
            "step": {
                "step_index": index,
                "name": name,
                "status": RunStatus.skipped.value,
                "duration_ms": 0,
                "response_data": result.response_data,
                "error_message": reason,
            },
        },
    )


async def run_api_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict):
    evidence_redact_fields = (case.config or {}).get("dataset_redact_fields") or []
    cfg = case.config  # 用例配置 JSON
    steps = cfg.get("steps", [{"name": "主请求", **cfg}])
    policy = build_api_scenario_policy(cfg)
    if not isinstance(steps, list):
        raise ApiScenarioError("API 场景 steps 必须是数组")

    reuse_api_session = policy.session_lifecycle == "reuse"
    project_id: int | None = None
    try:
        project_id = await _resolve_case_project_id(db, case)
    except Exception:
        project_id = None
    shared_client: httpx.AsyncClient | None = None
    if reuse_api_session:
        if project_id is not None:
            shared_client = httpx.AsyncClient()
            try:
                apply_cookies(shared_client.cookies, await load_project_api_session(project_id))
            except Exception:
                # Optional session reuse must not make an otherwise valid API case fail.
                pass

    context: dict = {**extra_vars}  # 变量上下文
    all_passed = True
    total_start = time.monotonic()
    completed_status: dict[int, RunStatus] = {}
    stop_remaining = False
    oauth_token_cache: dict[str, tuple[str, float]] = {}

    for idx, step in enumerate(steps):
        step_name = step.get("name", f"Step {idx + 1}")
        dependencies = step_dependencies(step, idx)
        failed_dependencies = [
            dependency
            for dependency in dependencies
            if completed_status.get(dependency) in {RunStatus.failed, RunStatus.error, RunStatus.skipped}
        ]
        if stop_remaining or failed_dependencies:
            reason = (
                "场景失败策略已停止后续步骤"
                if stop_remaining
                else f"依赖步骤未通过: {', '.join(str(item + 1) for item in failed_dependencies)}"
            )
            await _record_skipped_scenario_step(db, run, idx, step_name, reason)
            completed_status[idx] = RunStatus.skipped
            all_passed = False
            continue
        request_context = context if policy.context_scope == "scenario" else {**extra_vars}
        with _tracer.start_as_current_span(f"step.{idx}") as step_span:
            step_span.set_attribute("step.index", idx)
            step_span.set_attribute("step.name", step_name)

            step_start = time.monotonic()
            step_result = StepResult(
                run_id=run.id,
                step_index=idx,
                name=step_name,
                status=RunStatus.running,
            )
            db.add(step_result)
            await db.commit()

            request_data = {}
            response_data = {}
            assertion_records: list[dict] = []
            extraction_records: list[dict] = []
            error_msg = None
            step_status = RunStatus.passed

            try:
                hook_summaries = execute_api_hooks(step.get("pre_actions"), request_context)
                # 变量替换
                url = _render(step.get("url", ""), request_context)
                method = step.get("method", "GET").upper()
                headers = {k: _render(v, request_context) for k, v in step.get("headers", {}).items()}
                params = {k: _render(v, request_context) for k, v in step.get("params", {}).items()}
                cookies = {k: _render(v, request_context) for k, v in step.get("cookies", {}).items()}
                body = step.get("body")
                timeout = step.get("timeout", 30)
                step_span.set_attribute("http.request.method", method)
                step_span.set_attribute("http.url", url)

                # 认证注入
                auth_cfg = step.get("auth", {})
                auth_type = auth_cfg.get("type")
                if auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {_render(auth_cfg.get('token', ''), context)}"
                elif auth_type == "basic":
                    import base64

                    cred = base64.b64encode(f"{auth_cfg.get('username')}:{auth_cfg.get('password')}".encode()).decode()
                    headers["Authorization"] = f"Basic {cred}"
                elif auth_type == "apikey":
                    header_name = _render(auth_cfg.get("header", "X-API-Key"), context).strip()
                    header_value = _render(auth_cfg.get("value", ""), context)
                    if header_name:
                        headers[header_name] = header_value

                request_kwargs, request_body_for_record = await _build_request_kwargs(
                    step,
                    request_context,
                    headers=headers,
                    params=params,
                    cookies=cookies,
                    project_id=project_id,
                )
                if auth_type == "digest":
                    request_kwargs["auth"] = build_digest_auth(auth_cfg, lambda value: _render(value, context))
                elif auth_type == "oauth2_client_credentials":
                    headers["Authorization"] = await resolve_oauth2_client_credentials_token(
                        auth_cfg,
                        lambda value: _render(value, context),
                        float(timeout),
                        oauth_token_cache,
                    )
                request_data = {
                    "method": method,
                    "url": url,
                    "headers": headers,
                    "params": params,
                    "cookies": cookies,
                    "body": request_body_for_record,
                }
                if shared_client is not None and cookies:
                    shared_client.cookies.update(cookies)
                    request_kwargs.pop("cookies", None)
                if shared_client is not None:
                    resp, streamed_body = await _send_request(
                        shared_client,
                        method,
                        url,
                        timeout,
                        request_kwargs,
                        step.get("response_type"),
                        step.get("sse_max_events", 100),
                    )
                else:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp, streamed_body = await _send_request(
                            client,
                            method,
                            url,
                            timeout,
                            request_kwargs,
                            step.get("response_type"),
                            step.get("sse_max_events", 100),
                        )

                duration = int((time.monotonic() - step_start) * 1000)
                resp_body = (
                    streamed_body
                    if streamed_body is not None
                    else _parse_response_body(resp, step.get("response_type"))
                )

                response_data = response_contract(
                    "http",
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    body=resp_body,
                    duration_ms=duration,
                )
                step_span.set_attribute("http.response.status_code", resp.status_code)

                # 变量提取
                for extraction in step.get("extractions", []):
                    val = _extract_value(
                        resp_body,
                        extraction.get("expression", ""),
                        extraction.get("type", "jsonpath"),
                    )
                    if val is not None:
                        request_context[extraction["variable"]] = val
                    extraction_records.append(
                        extraction_result(
                            extraction,
                            value=val,
                            success=val is not None,
                            error=None if val is not None else "未提取到值",
                        )
                    )
                response_data["extractions"] = extraction_records

                hook_summaries.extend(
                    execute_api_hooks(
                        step.get("post_actions"),
                        request_context,
                        response_body=resp_body,
                        response_headers=dict(resp.headers),
                    )
                )
                if hook_summaries:
                    response_data["hook_actions"] = hook_summaries

                # 断言
                assertions = await _resolve_schema_assertions(db, step.get("assertions", []), project_id)
                for assertion in assertions:
                    passed, msg = _assert(assertion, resp, resp_body, duration)
                    assertion_records.append(assertion_result(assertion, passed=passed, message=msg))
                    if not passed:
                        step_status = RunStatus.failed
                        all_passed = False
                        error_msg = msg
                        break
                response_data["assertions"] = assertion_records

            except Exception as e:
                step_status = RunStatus.error
                all_passed = False
                error_msg = str(e)
                step_span.record_exception(e)

            step_result.status = step_status
            step_result.duration_ms = int((time.monotonic() - step_start) * 1000)
            persisted_request_data = redact_execution_evidence(request_data, evidence_redact_fields)
            persisted_response_data = redact_execution_evidence(response_data, evidence_redact_fields)
            step_result.request_data = persisted_request_data
            step_result.response_data = persisted_response_data
            step_result.error_message = error_msg
            needs_healing = apply_healing_hook(step_result)
            await db.commit()
            if needs_healing:
                enqueue_diagnosis(step_result.id)

            step_span.set_attribute("step.status", step_status.value)
            step_span.set_attribute("step.duration_ms", step_result.duration_ms)
            if step_status in (RunStatus.failed, RunStatus.error):
                step_span.set_status(Status(StatusCode.ERROR, error_msg or step_status.value))

            completed_status[idx] = step_status
            if step_status in (RunStatus.failed, RunStatus.error) and policy.failure_strategy == "stop":
                stop_remaining = True

            # 推送步骤结果
            await _safe_publish_run_event(
                run.id,
                {
                    "type": "step_result",
                    "run_id": run.id,
                    "step": {
                        "step_index": idx,
                        "name": step_result.name,
                        "status": step_status.value,
                        "duration_ms": step_result.duration_ms,
                        "request_data": persisted_request_data,
                        "response_data": persisted_response_data,
                        "error_message": error_msg,
                    },
                },
            )

    if shared_client is not None:
        try:
            if project_id is not None:
                await save_project_api_session(project_id, serialize_cookies(shared_client.cookies))
        except Exception:
            # Redis is an optional persistence layer for this opt-in feature.
            pass
        finally:
            await shared_client.aclose()

    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    await db.commit()

    # iter3 多 step 综合诊断（异步入队，不阻塞 completed 推送）
    await maybe_enqueue_run_healing(db, run)

    # 推送执行完成
    await _safe_publish_run_event(
        run.id,
        {
            "type": "completed",
            "run_id": run.id,
            "status": run.status.value,
            "duration_ms": total_ms,
        },
    )


def _render(template: str, context: dict) -> str:
    """简单的 {{variable}} 占位符替换"""
    for k, v in context.items():
        template = template.replace(f"{{{{{k}}}}}", str(v))
    return template


async def _build_request_kwargs(
    step: dict,
    context: dict,
    *,
    headers: dict[str, str],
    params: dict[str, str],
    cookies: dict[str, str],
    project_id: int | None,
) -> tuple[dict, object]:
    """Build httpx request arguments while keeping file bytes out of run records."""
    body_type = step.get("body_type", "none")
    body = step.get("body")
    kwargs: dict = {"headers": headers, "params": params}
    record_body = body

    if body_type == "json":
        kwargs["json"] = body
    elif body_type == "form":
        kwargs["data"] = body
    elif body_type in {"raw", "xml"}:
        kwargs["content"] = _render(body if isinstance(body, str) else "", context)
        if body_type == "xml" and not any(key.lower() == "content-type" for key in headers):
            headers["Content-Type"] = "application/xml"
    elif body_type == "multipart":
        form_data: dict[str, str] = {}
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        record_parts: list[dict] = []
        for part in step.get("multipart", []):
            name = _render(str(part.get("name", "")), context).strip()
            if not name:
                continue
            part_type = part.get("type", "text")
            if part_type == "file":
                object_name = str(part.get("object_name", ""))
                expected_prefix = f"api-files/projects/{project_id}/" if project_id is not None else "api-files/"
                if not object_name.startswith(expected_prefix):
                    raise ValueError("multipart 文件引用无效，必须使用 API 请求文件上传返回的对象")
                content = await asyncio.to_thread(read_bytes, object_name)
                filename = _render(str(part.get("filename") or "upload.bin"), context)
                content_type = str(part.get("content_type") or "application/octet-stream")
                files.append((name, (filename, content, content_type)))
                record_parts.append(
                    {
                        "name": name,
                        "type": "file",
                        "filename": filename,
                        "object_name": object_name,
                        "content_type": content_type,
                        "size": len(content),
                    }
                )
            else:
                value = _render(str(part.get("value", "")), context)
                form_data[name] = value
                record_parts.append({"name": name, "type": "text", "value": value})
        kwargs["data"] = form_data
        kwargs["files"] = files
        record_body = record_parts
    elif body_type != "none":
        raise ValueError(f"不支持的请求体类型: {body_type}")

    if cookies:
        kwargs["cookies"] = cookies
    return kwargs, record_body


async def _send_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    timeout: float,
    request_kwargs: dict,
    response_type: str | None,
    sse_max_events: int,
) -> tuple[httpx.Response, list[dict] | None]:
    """Send a regular request or consume a bounded Server-Sent Events stream."""
    if response_type != "sse":
        return await client.request(method, url, timeout=timeout, **request_kwargs), None

    events: list[dict] = []
    max_events = max(1, min(int(sse_max_events), 1000))
    async with client.stream(method, url, timeout=timeout, **request_kwargs) as response:
        current_event = "message"
        data_lines: list[str] = []
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                current_event = line[6:].strip() or "message"
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            elif not line.strip() and data_lines:
                events.append({"event": current_event, "data": "\n".join(data_lines)})
                current_event = "message"
                data_lines = []
                if len(events) >= max_events:
                    break
        if data_lines and len(events) < max_events:
            events.append({"event": current_event, "data": "\n".join(data_lines)})
        return response, events


def _parse_response_body(resp: httpx.Response, response_type: str | None):
    if response_type == "xml":
        return resp.text
    try:
        return resp.json()
    except Exception:
        return resp.text


def _jsonpath_extract(data, expression: str):
    try:
        matches = jp_parse(expression).find(data)
        return matches[0].value if matches else None
    except Exception:
        return None


def _xpath_extract(xml_text: str, expression: str):
    """Extract text/attribute values using ElementTree's safe XPath subset."""
    if not isinstance(xml_text, str) or not xml_text.strip() or not expression.strip():
        return None
    try:
        root = ET.fromstring(xml_text)
        path = expression.strip()
        attribute = None
        if "/@" in path:
            path, attribute = path.rsplit("/@", 1)
        if path in {".", ""}:
            node = root
        else:
            if path.startswith("//"):
                path = f".{path}"
            elif path.startswith("/"):
                path = f".{path}"
            node = root.find(path)
        if node is None:
            return None
        if attribute:
            return node.attrib.get(attribute)
        return node.text if node.text is not None else node
    except (ET.ParseError, SyntaxError, ValueError):
        return None


def _extract_value(data, expression: str, expression_type: str = "jsonpath"):
    if expression_type == "xpath":
        return _xpath_extract(data, expression)
    return _jsonpath_extract(data, expression)


def _load_schema(schema):
    if isinstance(schema, str):
        try:
            return json.loads(schema)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON Schema 不是合法 JSON: {exc.msg}") from exc
    return schema


def _schema_valid(body, schema) -> tuple[bool, str]:
    try:
        from jsonschema import Draft202012Validator

        schema = _load_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(body), key=lambda error: list(error.path))
        if errors:
            error = errors[0]
            path = ".".join(str(item) for item in error.path) or "$"
            return False, f"JSON Schema 校验失败 [{path}]: {error.message}"
        return True, ""
    except ImportError as exc:
        raise ValueError("JSON Schema 校验依赖未安装") from exc


def _assert(assertion: dict, resp: httpx.Response, body, duration_ms: int) -> tuple[bool, str]:
    target = assertion.get("target")  # status_code / body / header / duration
    operator = assertion.get("operator")  # eq / contains / gt / lt / exists
    expected = assertion.get("expected")
    expression = assertion.get("expression", "")
    expression_type = assertion.get("expression_type", assertion.get("type", "jsonpath"))

    if target == "expression" or operator in {"expression", "safe_expression"}:
        expression_text = str(expression or expected or "")
        try:
            value = evaluate_safe_expression(
                expression_text,
                {
                    "status_code": resp.status_code,
                    "body": body,
                    "headers": dict(resp.headers),
                    "response_time_ms": duration_ms,
                },
            )
        except SafeExpressionError as exc:
            return False, f"受限表达式无效: {exc}"
        if not bool(value):
            return False, f"表达式断言失败: {expression_text}"
        return True, ""

    if target in {"json_schema", "schema"}:
        try:
            valid, message = _schema_valid(body, assertion.get("schema", expected))
        except ValueError as exc:
            return False, str(exc)
        operator = operator or "valid"
        ok = valid if operator == "valid" else not valid if operator == "invalid" else False
        if not ok:
            return False, message or f"JSON Schema 断言失败，实际响应符合 Schema: {valid}"
        return True, ""

    actual = None
    if target == "status_code":
        actual = resp.status_code
    elif target == "body":
        actual = _extract_value(body, expression, expression_type) if expression else body
    elif target == "header":
        actual = resp.headers.get(expression)
    elif target == "duration":
        actual = duration_ms

    if operator == "eq":
        ok = str(actual) == str(expected)
    elif operator == "contains":
        ok = expected in str(actual)
    elif operator == "gt":
        ok = float(actual) > float(expected)
    elif operator == "lt":
        ok = float(actual) < float(expected)
    elif operator == "exists":
        ok = actual is not None
    elif operator == "not_exists":
        ok = actual is None
    else:
        return False, f"未知断言操作符: {operator}"

    if not ok:
        return False, f"断言失败 [{target}] 期望: {expected}, 实际: {actual}"
    return True, ""
