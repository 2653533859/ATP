"""GraphQL 接口测试执行器。"""

import asyncio
import json
import time

import httpx
import websockets
from jsonpath_ng import parse as jp_parse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import TestRun, TestCase, StepResult, RunStatus
from app.core.redis_client import publish_run_event
from app.services.dataset_execution import redact_execution_evidence
from app.services.api_auth import build_digest_auth, resolve_oauth2_client_credentials_token
from app.services.execution_contract import assertion_result, extraction_result, response_contract
from app.services.step_result_collector import StepResultBatchCollector
from app.services.template_variables import render_template_string, render_template_value
from app.worker.executors._assertion_helpers import (
    build_basic_auth_header,
    collect_auth_redact_fields,
    compare_assertion_operator,
    render_recursive,
)
from app.core.tracing import inject_w3c_trace_headers


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        return


async def run_graphql_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict):
    cfg = case.config
    evidence_redact_fields = cfg.get("dataset_redact_fields") or []
    steps = cfg.get("steps", [])

    context: dict = {**extra_vars}
    all_passed = True
    total_start = time.monotonic()
    oauth_token_cache: dict[str, tuple[str, float]] = {}
    step_collector = StepResultBatchCollector(db)
    for idx, step in enumerate(steps):
        step_start = time.monotonic()
        step_result = StepResult(
            run_id=run.id,
            step_index=idx,
            name=step.get("name", f"Step {idx + 1}"),
            status=RunStatus.running,
            duration_ms=0,
        )

        request_data = {}
        response_data = {}
        assertion_records: list[dict] = []
        extraction_records: list[dict] = []
        error_msg = None
        step_status = RunStatus.passed
        step_redact_fields = list(evidence_redact_fields)

        try:
            endpoint = _render(step.get("endpoint", ""), context)
            query = _render(step.get("query", ""), context)
            variables = step.get("variables") or {}
            # 变量值递归模板替换（保留非字符串基本类型）
            rendered_vars = render_recursive(variables, lambda text: _render(text, context))
            operation_name = step.get("operation_name") or None
            timeout = step.get("timeout", 30)

            headers = {"Content-Type": "application/json"}
            for k, v in step.get("headers", {}).items():
                headers[k] = _render(v, context)

            # 认证注入
            auth_cfg = step.get("auth", {})
            auth_type = auth_cfg.get("type")
            step_redact_fields.extend(collect_auth_redact_fields(auth_cfg, lambda value: _render(str(value), context)))
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {_render(auth_cfg.get('token', ''), context)}"
            elif auth_type == "basic":
                headers["Authorization"] = build_basic_auth_header(auth_cfg, lambda value: _render(str(value), context))
            elif auth_type == "apikey":
                header_name = _render(auth_cfg.get("header", "X-API-Key"), context).strip()
                header_value = _render(auth_cfg.get("value", ""), context)
                if header_name:
                    headers[header_name] = header_value

            request_auth = None
            if auth_type == "digest":
                request_auth = build_digest_auth(auth_cfg, lambda value: _render(value, context))
            elif auth_type == "oauth2_client_credentials":
                headers["Authorization"] = await resolve_oauth2_client_credentials_token(
                    auth_cfg,
                    lambda value: _render(value, context),
                    float(timeout),
                    oauth_token_cache,
                )
            headers = inject_w3c_trace_headers(
                headers,
                run_id=getattr(run, "id", None),
                case_id=getattr(case, "id", None),
                trace_id=getattr(run, "trace_id", None),
            )

            # 构造 GraphQL 请求体
            gql_body: dict = {"query": query}
            if rendered_vars:
                gql_body["variables"] = rendered_vars
            if operation_name:
                gql_body["operationName"] = operation_name

            operation_type = str(step.get("operation_type") or "query").lower()
            is_subscription = operation_type == "subscription"
            request_data = {
                "method": "WS" if is_subscription else "POST",
                "url": endpoint,
                "headers": headers,
                "body": gql_body,
            }

            if is_subscription:
                if request_auth is not None:
                    raise ValueError("GraphQL Subscription 暂不支持 Digest 认证")
                raw_sub_url = _render(str(step.get("subscription_url") or endpoint), context)
                subscription_url = _subscription_url(raw_sub_url)
                request_data["url"] = subscription_url
                rendered_sub_step = {
                    **step,
                    "connection_payload": render_recursive(
                        step.get("connection_payload") or {}, lambda text: _render(text, context)
                    ),
                }
                messages = await _run_subscription(
                    subscription_url, headers, gql_body, rendered_sub_step, float(timeout)
                )
                resp_body = messages[-1]["payload"] if messages else None
                duration = int((time.monotonic() - step_start) * 1000)
                resp = httpx.Response(status_code=101)
                response_data = response_contract(
                    "graphql",
                    status_code=101,
                    headers={},
                    body=resp_body,
                    duration_ms=duration,
                    metadata={"operation_type": "subscription", "messages": messages},
                )
                response_data["messages"] = messages
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(endpoint, headers=headers, json=gql_body, auth=request_auth)

                duration = int((time.monotonic() - step_start) * 1000)
                json_parse_failed = False
                try:
                    resp_body = resp.json()
                except Exception:
                    resp_body = resp.text
                    json_parse_failed = True

                response_data = response_contract(
                    "graphql",
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    body=resp_body,
                    duration_ms=duration,
                )

            # 变量提取
            for extraction in step.get("extractions", []):
                val = _jsonpath_extract(resp_body, extraction["expression"])
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
            response_data["extractions"] = extraction_records

            # 断言
            assertions = step.get("assertions", [])
            for assertion in assertions:
                rendered_assertion = _render_assertion(assertion, context)
                passed, msg = _assert(rendered_assertion, resp, resp_body, duration)
                assertion_records.append(assertion_result(rendered_assertion, passed=passed, message=msg))
                if not passed:
                    step_status = RunStatus.failed
                    all_passed = False
                    error_msg = msg
                    break

            # 默认协议校验：仅在显式断言全部通过（含零断言）且未显式接管对应字段时生效
            if step_status == RunStatus.passed and not is_subscription:
                assertion_targets = {a.get("target") for a in assertions if isinstance(a, dict)}
                if resp.status_code >= 400 and "status_code" not in assertion_targets:
                    error_msg = f"GraphQL 请求失败: HTTP {resp.status_code}"
                    step_status = RunStatus.failed
                    all_passed = False
                    assertion_records.append(
                        assertion_result(
                            {"target": "status_code", "operator": "lt", "expected": 400, "default": True},
                            passed=False,
                            message=error_msg,
                        )
                    )
                elif (
                    (json_parse_failed or not isinstance(resp_body, dict))
                    and not (resp.status_code >= 400 and "status_code" in assertion_targets)
                    and "body" not in assertion_targets
                ):
                    error_msg = f"GraphQL 响应不是有效的 JSON 对象 (HTTP {resp.status_code})"
                    step_status = RunStatus.failed
                    all_passed = False
                    assertion_records.append(
                        assertion_result(
                            {"target": "body", "operator": "is_json_object", "expected": True, "default": True},
                            passed=False,
                            message=error_msg,
                        )
                    )
                elif (
                    isinstance(resp_body, dict)
                    and resp_body.get("errors")
                    and "graphql_errors" not in assertion_targets
                    and "body" not in assertion_targets
                ):
                    error_msg = f"GraphQL 返回错误: {resp_body.get('errors')}"
                    step_status = RunStatus.failed
                    all_passed = False
                    assertion_records.append(
                        assertion_result(
                            {"target": "graphql_errors", "operator": "not_exists", "default": True},
                            passed=False,
                            message=error_msg,
                        )
                    )

            response_data["assertions"] = assertion_records

        except Exception as e:
            step_status = RunStatus.error
            all_passed = False
            error_msg = str(e)

        step_result.status = step_status
        step_result.duration_ms = int((time.monotonic() - step_start) * 1000)
        persisted_request_data = redact_execution_evidence(request_data, step_redact_fields)
        persisted_response_data = redact_execution_evidence(response_data, step_redact_fields)
        step_result.request_data = persisted_request_data
        step_result.response_data = persisted_response_data
        step_result.error_message = error_msg
        await step_collector.add(step_result)

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

    await step_collector.flush()
    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    await db.commit()

    await _safe_publish_run_event(
        run.id,
        {
            "type": "completed",
            "run_id": run.id,
            "status": run.status.value,
            "duration_ms": total_ms,
        },
    )


def _subscription_url(value: str) -> str:
    if value.startswith("https://"):
        return f"wss://{value[8:]}"
    if value.startswith("http://"):
        return f"ws://{value[7:]}"
    if value.startswith(("ws://", "wss://")):
        return value
    raise ValueError("GraphQL Subscription 地址必须使用 http(s):// 或 ws(s)://")


async def _run_subscription(url: str, headers: dict, gql_body: dict, step: dict, timeout: float) -> list[dict]:
    """按 graphql-transport-ws 协议读取有界事件流。"""
    max_messages = max(1, min(int(step.get("max_messages", 1)), 100))
    reconnect_attempts = max(0, min(int(step.get("reconnect_attempts", 0)), 5))
    reconnect_delay = max(0, min(int(step.get("reconnect_delay_ms", 500)), 30_000)) / 1000
    connection_payload = step.get("connection_payload") or {}
    last_error: Exception | None = None

    for attempt in range(reconnect_attempts + 1):
        try:
            messages: list[dict] = []
            async with websockets.connect(
                url,
                additional_headers=headers or None,
                subprotocols=["graphql-transport-ws"],
                open_timeout=timeout,
                close_timeout=5,
            ) as ws:
                await ws.send(
                    json.dumps({"type": "connection_init", "payload": connection_payload}, ensure_ascii=False)
                )
                ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                if ack.get("type") != "connection_ack":
                    raise RuntimeError(f"GraphQL Subscription 握手失败: {ack.get('type', 'unknown')}")
                operation_id = str(step.get("subscription_id") or "1")
                await ws.send(
                    json.dumps(
                        {"id": operation_id, "type": "subscribe", "payload": gql_body},
                        ensure_ascii=False,
                    )
                )
                while len(messages) < max_messages:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    message = json.loads(raw)
                    message_type = message.get("type")
                    if message_type == "next":
                        messages.append({"type": "next", "payload": message.get("payload")})
                    elif message_type == "error":
                        raise RuntimeError(f"GraphQL Subscription 返回错误: {message.get('payload')}")
                    elif message_type == "complete":
                        break
                    elif message_type == "ping":
                        await ws.send(json.dumps({"type": "pong", "payload": message.get("payload")}))
                await ws.send(json.dumps({"id": operation_id, "type": "complete"}))
                return messages
        except Exception as exc:
            last_error = exc
            if attempt >= reconnect_attempts:
                raise
            if reconnect_delay:
                await asyncio.sleep(reconnect_delay)
    raise RuntimeError("GraphQL Subscription 连接失败") from last_error


def _render(template: str, context: dict) -> str:
    """渲染 {{variable}} 与内置 {{$dynamic}} 占位符。"""
    return render_template_string(template, context)


def _jsonpath_extract(data, expression: str):
    try:
        matches = jp_parse(expression).find(data)
        return matches[0].value if matches else None
    except Exception:
        return None


def _render_assertion(assertion: dict, context: dict | None) -> dict:
    """按上下文单次渲染断言期望值与表达式，空 dict 仍允许展开内置 {{$...}} 变量。"""
    if context is None:
        return assertion
    updated: dict = {}
    expected = assertion.get("expected")
    if expected is not None:
        rendered_expected = render_template_value(expected, context, preserve_type=True)
        if rendered_expected != expected:
            updated["expected"] = rendered_expected
    expression = assertion.get("expression")
    if isinstance(expression, str) and "{{" in expression:
        rendered_expression = _render(expression, context)
        if rendered_expression != expression:
            updated["expression"] = rendered_expression
    return {**assertion, **updated} if updated else assertion


def _assert(
    assertion: dict,
    resp: httpx.Response,
    body,
    duration_ms: int,
    context: dict | None = None,
) -> tuple[bool, str]:
    if context is not None:
        assertion = _render_assertion(assertion, context)
    target = assertion.get("target")
    operator = assertion.get("operator")
    expected = assertion.get("expected")
    expression = assertion.get("expression", "")

    actual = None
    if target == "status_code":
        actual = resp.status_code
    elif target == "body":
        actual = _jsonpath_extract(body, expression) if expression else body
    elif target == "header":
        actual = resp.headers.get(expression)
    elif target == "duration":
        actual = duration_ms
    elif target == "graphql_errors":
        # 特殊断言：检查 GraphQL errors 字段
        errors = body.get("errors") if isinstance(body, dict) else None
        if operator == "not_exists":
            ok = errors is None or len(errors) == 0
            if not ok:
                return False, f"断言失败 [graphql_errors] 期望无错误, 实际: {errors}"
            return True, ""
        elif operator == "exists":
            ok = errors is not None and len(errors) > 0
            if not ok:
                return False, "断言失败 [graphql_errors] 期望存在错误, 实际无错误"
            return True, ""
        else:
            # 对 errors 数组整体做断言
            actual = errors

    return compare_assertion_operator(operator, actual, expected, target=str(target or ""))
