"""HTTP/REST 接口测试执行器"""
import time
import httpx
from jsonpath_ng import parse as jp_parse
from opentelemetry.trace import Status, StatusCode
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.otel import get_tracer
from app.models.case import TestRun, TestCase, StepResult, RunStatus
from app.core.redis_client import publish_run_event

_tracer = get_tracer("atp.executor.api")


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        # 实时通知是 best-effort，不影响执行结果落库
        return


async def run_api_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict):
    cfg = case.config  # 用例配置 JSON
    steps = cfg.get("steps", [{"name": "主请求", **cfg}])

    context: dict = {**extra_vars}  # 变量上下文
    all_passed = True
    total_start = time.monotonic()

    for idx, step in enumerate(steps):
        step_name = step.get("name", f"Step {idx + 1}")
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
            error_msg = None
            step_status = RunStatus.passed

            try:
                # 变量替换
                url = _render(step.get("url", ""), context)
                method = step.get("method", "GET").upper()
                headers = {k: _render(v, context) for k, v in step.get("headers", {}).items()}
                params = {k: _render(v, context) for k, v in step.get("params", {}).items()}
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
                    cred = base64.b64encode(
                        f"{auth_cfg.get('username')}:{auth_cfg.get('password')}".encode()
                    ).decode()
                    headers["Authorization"] = f"Basic {cred}"
                elif auth_type == "apikey":
                    header_name = _render(auth_cfg.get("header", "X-API-Key"), context).strip()
                    header_value = _render(auth_cfg.get("value", ""), context)
                    if header_name:
                        headers[header_name] = header_value

                request_data = {"method": method, "url": url, "headers": headers, "params": params, "body": body}

                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.request(
                        method, url, headers=headers, params=params,
                        json=body if step.get("body_type") == "json" else None,
                        data=body if step.get("body_type") == "form" else None,
                        content=body if step.get("body_type") == "raw" else None,
                    )

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
                step_span.set_attribute("http.response.status_code", resp.status_code)

                # 变量提取
                for extraction in step.get("extractions", []):
                    val = _jsonpath_extract(resp_body, extraction["expression"])
                    if val is not None:
                        context[extraction["variable"]] = val

                # 断言
                assertions = step.get("assertions", [])
                for assertion in assertions:
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
                step_span.record_exception(e)

            step_result.status = step_status
            step_result.duration_ms = int((time.monotonic() - step_start) * 1000)
            step_result.request_data = request_data
            step_result.response_data = response_data
            step_result.error_message = error_msg
            await db.commit()

            step_span.set_attribute("step.status", step_status.value)
            step_span.set_attribute("step.duration_ms", step_result.duration_ms)
            if step_status in (RunStatus.failed, RunStatus.error):
                step_span.set_status(Status(StatusCode.ERROR, error_msg or step_status.value))

            # 推送步骤结果
            await _safe_publish_run_event(run.id, {
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
            })

    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    await db.commit()

    # 推送执行完成
    await _safe_publish_run_event(run.id, {
        "type": "completed",
        "run_id": run.id,
        "status": run.status.value,
        "duration_ms": total_ms,
    })


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
    target = assertion.get("target")  # status_code / body / header / duration
    operator = assertion.get("operator")  # eq / contains / gt / lt / exists
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
    else:
        return False, f"未知断言操作符: {operator}"

    if not ok:
        return False, f"断言失败 [{target}] 期望: {expected}, 实际: {actual}"
    return True, ""
