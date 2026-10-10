import asyncio
import json
import logging
import re
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.otel import get_tracer
from app.core.redis_client import publish_run_event
from app.models.case import RunStatus, StepResult, TestCase, TestRun
from app.services.dataset_execution import redact_execution_evidence
from app.services.execution_contract import assertion_result, extraction_result, response_contract
from app.services.step_result_collector import StepResultBatchCollector

logger = logging.getLogger(__name__)
_tracer = get_tracer("atp.executor.multiprotocol")
VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def render_template(text: Any, context: dict[str, Any]) -> Any:
    if not isinstance(text, str):
        return text
    return VAR_PATTERN.sub(lambda m: str(context.get(m.group(1), m.group(0))), text)


def render_dict(data: Any, context: dict[str, Any]) -> Any:
    if isinstance(data, dict):
        return {k: render_dict(v, context) for k, v in data.items()}
    if isinstance(data, list):
        return [render_dict(v, context) for v in data]
    return render_template(data, context)


def extract_json_value(data: Any, expression: str) -> Any:
    """提取字段值，支持简单 dot 路径与基础 JsonPath。"""
    if not expression or not isinstance(data, (dict, list)):
        return None
    try:
        from jsonpath_ng import parse as jp_parse

        expr = jp_parse(expression)
        matches = expr.find(data)
        if matches:
            return matches[0].value
    except Exception:
        pass
    # 简易 dot path 降级
    curr = data
    for part in expression.strip("$.").split("."):
        if not part:
            continue
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
            curr = curr[int(part)]
        else:
            return None
    return curr


def evaluate_assertion(assertion: dict[str, Any], actual_val: Any) -> tuple[bool, str | None]:
    operator = assertion.get("operator", "eq")
    expected = assertion.get("expected")

    if operator == "eq":
        passed = str(actual_val) == str(expected)
        msg = None if passed else f"断言失败: 期望 '{expected}', 实际得到 '{actual_val}'"
    elif operator == "neq":
        passed = str(actual_val) != str(expected)
        msg = None if passed else f"断言失败: 期望不等于 '{expected}'"
    elif operator == "contains":
        passed = str(expected) in str(actual_val)
        msg = None if passed else f"断言失败: '{actual_val}' 不包含 '{expected}'"
    elif operator == "exists":
        passed = actual_val is not None
        msg = None if passed else "断言失败: 字段不存在或为 None"
    else:
        passed = str(actual_val) == str(expected)
        msg = None if passed else f"断言失败: '{actual_val}' != '{expected}'"

    return passed, msg


async def _apply_http_auth(step: dict[str, Any], headers: dict[str, str], context: dict[str, Any]) -> dict[str, Any]:
    """按标准接口执行器的语义注入认证，避免多协议步骤静默丢弃认证配置。"""
    auth_cfg = step.get("auth") or {}
    auth_type = auth_cfg.get("type")
    extra_kwargs: dict[str, Any] = {}
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {render_template(auth_cfg.get('token', ''), context)}"
    elif auth_type == "basic":
        import base64

        cred = base64.b64encode(f"{auth_cfg.get('username')}:{auth_cfg.get('password')}".encode()).decode()
        headers["Authorization"] = f"Basic {cred}"
    elif auth_type == "apikey":
        header_name = render_template(auth_cfg.get("header", "X-API-Key"), context).strip()
        header_value = render_template(auth_cfg.get("value", ""), context)
        if header_name:
            headers[header_name] = header_value
    elif auth_type == "digest":
        from app.services.api_auth import build_digest_auth

        extra_kwargs["auth"] = build_digest_auth(auth_cfg, lambda value: render_template(value, context))
    elif auth_type == "oauth2_client_credentials":
        from app.services.api_auth import resolve_oauth2_client_credentials_token

        # 每条步骤独立取 token，避免跨运行共享凭据缓存。
        headers["Authorization"] = await resolve_oauth2_client_credentials_token(
            auth_cfg,
            lambda value: render_template(value, context),
            float(step.get("timeout", 15.0)),
            {},
        )
    return extra_kwargs


def _build_http_request_kwargs(
    step: dict[str, Any], context: dict[str, Any], headers: dict[str, str], params: dict[str, str]
) -> tuple[dict[str, Any], Any]:
    """构造请求体参数，与标准接口执行器的 body_type 形状保持一致。

    兼容多协议步骤既有简写 ``{"json": ...}``；遇到本执行器尚未支持的形状时显式
    报错，而不是静默丢弃请求体。
    """
    if "body_type" in step:
        body_type = step.get("body_type") or "none"
        body = step.get("body")
    elif "json" in step:
        body_type = "json"
        body = step.get("json")
    else:
        body_type = "none"
        body = None

    request_kwargs: dict[str, Any] = {"headers": headers, "params": params}
    record_body: Any = None
    if body_type == "json":
        record_body = render_dict(body, context)
        request_kwargs["json"] = record_body
    elif body_type == "form":
        record_body = render_dict(body, context)
        request_kwargs["data"] = record_body
    elif body_type in {"raw", "xml"}:
        record_body = render_template(body if isinstance(body, str) else "", context)
        request_kwargs["content"] = record_body
        if body_type == "xml" and not any(key.lower() == "content-type" for key in headers):
            headers["Content-Type"] = "application/xml"
    elif body_type == "multipart":
        raise ValueError("多协议 HTTP 步骤暂不支持 multipart 请求体，请改用标准接口执行器")
    elif body_type != "none":
        raise ValueError(f"不支持的请求体类型: {body_type}")
    return request_kwargs, record_body


async def _execute_http_step(step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    import httpx

    url = render_template(step.get("url", ""), context)
    method = step.get("method", "GET").upper()
    headers = render_dict(step.get("headers", {}), context)
    params = render_dict(step.get("params", {}), context)
    cookies = {key: render_template(value, context) for key, value in (step.get("cookies") or {}).items()}
    timeout = float(step.get("timeout", 15.0))

    extra_kwargs = await _apply_http_auth(step, headers, context)
    request_kwargs, record_body = _build_http_request_kwargs(step, context, headers, params)
    request_kwargs.update(extra_kwargs)
    if cookies:
        request_kwargs["cookies"] = cookies

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(method=method, url=url, **request_kwargs)

    duration = int((time.monotonic() - start) * 1000)
    try:
        body = resp.json()
    except Exception:
        body = resp.text

    return {
        "status_code": resp.status_code,
        "body": body,
        "headers": dict(resp.headers),
        "duration_ms": duration,
        "raw_request": {
            "url": url,
            "method": method,
            "headers": headers,
            "params": params,
            "cookies": cookies,
            "body": record_body,
        },
    }


async def _execute_websocket_step(step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    url = render_template(step.get("url", ""), context)
    messages_cfg = render_dict(step.get("messages", []), context)
    timeout = float(step.get("timeout", 15.0))

    start = time.monotonic()
    received_messages: list[Any] = []
    import websockets

    async with websockets.connect(url, open_timeout=timeout) as ws:
        for msg in messages_cfg:
            action = msg.get("action", "send")
            if action == "send":
                payload = msg.get("payload")
                data_str = (
                    json.dumps(payload, ensure_ascii=False) if isinstance(payload, (dict, list)) else str(payload)
                )
                await ws.send(data_str)
            elif action == "receive":
                recv_timeout = float(msg.get("timeout", 5.0))
                raw_recv = await asyncio.wait_for(ws.recv(), timeout=recv_timeout)
                try:
                    parsed = json.loads(raw_recv)
                except Exception:
                    parsed = raw_recv
                received_messages.append(parsed)

    duration = int((time.monotonic() - start) * 1000)
    last_body = received_messages[-1] if received_messages else {}
    return {
        "status_code": 101,
        "body": last_body,
        "messages": received_messages,
        "duration_ms": duration,
        "raw_request": {"url": url, "messages_sent": messages_cfg},
    }


async def _execute_grpc_step(step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    target = render_template(step.get("target", ""), context)
    service = render_template(step.get("service", ""), context)
    method = render_template(step.get("method", ""), context)
    req_body = render_dict(step.get("body", {}), context)
    timeout = float(step.get("timeout", 15.0))

    start = time.monotonic()
    import grpc

    # 通过 grpc channel 进行调用
    channel = grpc.aio.insecure_channel(target)
    try:
        rpc_call = channel.unary_unary(
            f"/{service}/{method}",
            request_serializer=lambda x: json.dumps(x).encode("utf-8")
            if isinstance(x, dict)
            else str(x).encode("utf-8"),
            response_deserializer=lambda x: json.loads(x.decode("utf-8")) if x else {},
        )
        resp_data = await asyncio.wait_for(rpc_call(req_body), timeout=timeout)
        duration = int((time.monotonic() - start) * 1000)
        return {
            "status_code": 0,
            "body": resp_data,
            "duration_ms": duration,
            "raw_request": {"target": target, "service": service, "method": method, "body": req_body},
        }
    finally:
        await channel.close()


async def _execute_graphql_step(step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    import httpx

    endpoint = render_template(step.get("endpoint", step.get("url", "")), context)
    query = render_template(step.get("query", ""), context)
    variables = render_dict(step.get("variables", {}), context)
    headers = render_dict(step.get("headers", {}), context)
    timeout = float(step.get("timeout", 15.0))

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            endpoint,
            json={"query": query, "variables": variables},
            headers=headers,
        )

    duration = int((time.monotonic() - start) * 1000)
    try:
        body = resp.json()
    except Exception:
        body = resp.text

    return {
        "status_code": resp.status_code,
        "body": body,
        "headers": dict(resp.headers),
        "duration_ms": duration,
        "raw_request": {"endpoint": endpoint, "query": query, "variables": variables},
    }


async def run_multiprotocol_case(
    db: Any,
    run: Any,
    case: Any,
    extra_vars: dict[str, Any],
) -> None:
    """多协议穿梭场景流执行引擎 (MultiProtocolPipelineExecutor)。

    支持在单一测试用例场景流中混编 HTTP、WebSocket、GraphQL 与 gRPC 步骤，
    实现跨协议共享上下文提取、透传、断言与批处理持久化。
    """
    cfg = case.config or {}
    evidence_redact_fields = cfg.get("dataset_redact_fields") or []
    steps = cfg.get("steps", [])
    failure_strategy = cfg.get("failure_strategy", "continue")

    context: dict[str, Any] = {**extra_vars}
    all_passed = True
    total_start = time.monotonic()

    step_collector = StepResultBatchCollector(db)
    try:
        for idx, step in enumerate(steps):
            step_name = step.get("name", f"Step {idx + 1}")
            protocol = step.get("protocol", "http").lower().strip()
            if protocol in {"ws", "websocket"}:
                protocol = "websocket"
            elif protocol in {"rest", "http"}:
                protocol = "http"

            step_start = time.monotonic()
            step_result = StepResult(
                run_id=run.id,
                step_index=idx,
                name=step_name,
                status=RunStatus.running,
                duration_ms=0,
            )

            request_data: dict[str, Any] = {}
            response_data: dict[str, Any] = {}
            error_msg: str | None = None
            step_status = RunStatus.passed

            with _tracer.start_as_current_span(f"pipeline.step.{idx}.{protocol}") as step_span:
                step_span.set_attribute("step.index", idx)
                step_span.set_attribute("step.protocol", protocol)

                rendered_step = render_dict(step, context)
                try:
                    if protocol == "http":
                        exec_res = await _execute_http_step(rendered_step, context)
                    elif protocol == "websocket":
                        exec_res = await _execute_websocket_step(rendered_step, context)
                    elif protocol == "grpc":
                        exec_res = await _execute_grpc_step(rendered_step, context)
                    elif protocol == "graphql":
                        exec_res = await _execute_graphql_step(rendered_step, context)
                    else:
                        raise ValueError(f"未支持的多协议类型: '{protocol}'")

                    request_data = exec_res.get("raw_request") or {}
                    resp_body = exec_res.get("body")
                    duration_ms = exec_res.get("duration_ms", 0)

                    response_data = response_contract(
                        protocol,
                        status_code=exec_res.get("status_code", 200),
                        headers=exec_res.get("headers", {}),
                        body=resp_body,
                        duration_ms=duration_ms,
                    )

                    # 1. 跨协议参数池变量提取
                    extraction_records: list[dict[str, Any]] = []
                    for ext in step.get("extractions", []):
                        var_name = ext.get("variable")
                        expr = ext.get("expression", "")
                        val = extract_json_value(resp_body, expr)
                        if val is not None and var_name:
                            context[var_name] = val
                        extraction_records.append(
                            extraction_result(
                                ext,
                                value=val,
                                success=val is not None,
                                error=None if val is not None else "未提取到值",
                            )
                        )
                    if extraction_records:
                        response_data["extractions"] = extraction_records

                    # 2. 响应断言
                    assertion_records: list[dict[str, Any]] = []
                    for ass in step.get("assertions", []):
                        target = ass.get("target", "status_code")
                        if target == "status_code":
                            actual = exec_res.get("status_code")
                        elif target == "body":
                            actual = resp_body
                        else:
                            # 提取 body 字段值
                            actual = extract_json_value(resp_body, target)

                        passed, msg = evaluate_assertion(ass, actual)
                        assertion_records.append(assertion_result(ass, passed=passed, message=msg or ""))
                        if not passed:
                            step_status = RunStatus.failed
                            all_passed = False
                            error_msg = msg
                            break
                    if assertion_records:
                        response_data["assertions"] = assertion_records

                except Exception as exc:
                    step_status = RunStatus.error
                    all_passed = False
                    error_msg = str(exc)
                    step_span.record_exception(exc)

                step_result.status = step_status
                step_result.duration_ms = int((time.monotonic() - step_start) * 1000)
                persisted_request = redact_execution_evidence(request_data, evidence_redact_fields)
                persisted_response = redact_execution_evidence(response_data, evidence_redact_fields)
                step_result.request_data = persisted_request
                step_result.response_data = persisted_response
                step_result.error_message = error_msg

                await step_collector.add(step_result)

                # WebSocket 实时广播步骤进度
                await publish_run_event(
                    run.id,
                    {
                        "type": "step_result",
                        "run_id": run.id,
                        "step": {
                            "step_index": idx,
                            "name": step_name,
                            "protocol": protocol,
                            "status": step_status.value,
                            "duration_ms": step_result.duration_ms,
                            "request_data": persisted_request,
                            "response_data": persisted_response,
                            "error_message": error_msg,
                        },
                    },
                )

                if step_status in (RunStatus.failed, RunStatus.error) and failure_strategy == "stop":
                    break

    finally:
        await step_collector.flush()

    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    await db.commit()

    await publish_run_event(
        run.id,
        {
            "type": "completed",
            "run_id": run.id,
            "status": run.status.value,
            "duration_ms": total_ms,
        },
    )
