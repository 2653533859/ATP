"""GraphQL 接口测试执行器"""

import time
import httpx
from jsonpath_ng import parse as jp_parse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import TestRun, TestCase, StepResult, RunStatus
from app.core.redis_client import publish_run_event


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        return


async def run_graphql_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict):
    cfg = case.config
    steps = cfg.get("steps", [])

    context: dict = {**extra_vars}
    all_passed = True
    total_start = time.monotonic()

    for idx, step in enumerate(steps):
        step_start = time.monotonic()
        step_result = StepResult(
            run_id=run.id,
            step_index=idx,
            name=step.get("name", f"Step {idx + 1}"),
            status=RunStatus.running,
        )
        db.add(step_result)
        await db.commit()

        request_data = {}
        response_data = {}
        error_msg = None
        step_status = RunStatus.passed

        try:
            endpoint = _render(step.get("endpoint", ""), context)
            query = _render(step.get("query", ""), context)
            variables = step.get("variables") or {}
            # 变量值也做模板替换
            rendered_vars = {}
            for k, v in variables.items():
                rendered_vars[k] = _render(str(v), context) if isinstance(v, str) else v
            operation_name = step.get("operation_name") or None
            timeout = step.get("timeout", 30)

            headers = {"Content-Type": "application/json"}
            for k, v in step.get("headers", {}).items():
                headers[k] = _render(v, context)

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

            # 构造 GraphQL 请求体
            gql_body: dict = {"query": query}
            if rendered_vars:
                gql_body["variables"] = rendered_vars
            if operation_name:
                gql_body["operationName"] = operation_name

            request_data = {
                "method": "POST",
                "url": endpoint,
                "headers": headers,
                "body": gql_body,
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, headers=headers, json=gql_body)

            duration = int((time.monotonic() - step_start) * 1000)
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = resp.text

            response_data = {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp_body,
                "duration_ms": duration,
            }

            # 变量提取
            for extraction in step.get("extractions", []):
                val = _jsonpath_extract(resp_body, extraction["expression"])
                if val is not None:
                    context[extraction["variable"]] = val

            # 断言
            for assertion in step.get("assertions", []):
                passed, msg = _assert(assertion, resp, resp_body, duration)
                if not passed:
                    step_status = RunStatus.failed
                    all_passed = False
                    error_msg = msg
                    break

        except Exception as e:
            step_status = RunStatus.error
            all_passed = False
            error_msg = str(e)

        step_result.status = step_status
        step_result.duration_ms = int((time.monotonic() - step_start) * 1000)
        step_result.request_data = request_data
        step_result.response_data = response_data
        step_result.error_message = error_msg
        await db.commit()

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
                    "request_data": request_data,
                    "response_data": response_data,
                    "error_message": error_msg,
                },
            },
        )

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


def _render(template: str, context: dict) -> str:
    """简单的 {{variable}} 占位符替换"""
    for k, v in context.items():
        template = template.replace(f"{{{{{k}}}}}", str(v))
    return template


def _jsonpath_extract(data, expression: str):
    try:
        matches = jp_parse(expression).find(data)
        return matches[0].value if matches else None
    except Exception:
        return None


def _assert(assertion: dict, resp: httpx.Response, body, duration_ms: int) -> tuple[bool, str]:
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
