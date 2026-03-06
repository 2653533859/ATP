"""WebSocket 接口测试执行器"""
import asyncio
import json
import time
import websockets
from jsonpath_ng import parse as jp_parse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import TestRun, TestCase, StepResult, RunStatus
from app.core.redis_client import publish_run_event


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        return


async def run_websocket_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict):
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

        request_data: dict = {}
        response_data: dict = {}
        error_msg = None
        step_status = RunStatus.passed

        try:
            url = _render(step.get("url", ""), context)
            connect_timeout = step.get("timeout", 30)
            messages_cfg = step.get("messages", [])

            # 构建连接 headers
            headers = {}
            for k, v in step.get("headers", {}).items():
                headers[k] = _render(v, context)

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

            request_data = {"url": url, "headers": headers, "messages": []}
            message_log: list[dict] = []

            # 建立 WebSocket 连接
            async with websockets.connect(
                url,
                additional_headers=headers if headers else None,
                open_timeout=connect_timeout,
                close_timeout=5,
            ) as ws:
                # 遍历消息序列
                for msg_idx, msg_cfg in enumerate(messages_cfg):
                    action = msg_cfg.get("action", "send")

                    if action == "send":
                        data = _render(msg_cfg.get("data", ""), context)
                        data_type = msg_cfg.get("data_type", "text")

                        if data_type == "json":
                            # 尝试解析为 JSON 以验证格式，但仍以文本发送
                            try:
                                parsed = json.loads(data)
                                data = json.dumps(parsed, ensure_ascii=False)
                            except json.JSONDecodeError:
                                pass

                        await ws.send(data)
                        message_log.append({
                            "index": msg_idx,
                            "action": "send",
                            "data": data,
                            "data_type": data_type,
                        })

                    elif action == "receive":
                        recv_timeout = msg_cfg.get("timeout", 10)
                        try:
                            received = await asyncio.wait_for(
                                ws.recv(), timeout=recv_timeout
                            )
                        except asyncio.TimeoutError:
                            message_log.append({
                                "index": msg_idx,
                                "action": "receive",
                                "error": f"接收超时（{recv_timeout}s）",
                            })
                            step_status = RunStatus.failed
                            all_passed = False
                            error_msg = f"消息 #{msg_idx} 接收超时（{recv_timeout}s）"
                            break

                        # 尝试解析为 JSON
                        recv_body: any = received
                        if isinstance(received, str):
                            try:
                                recv_body = json.loads(received)
                            except (json.JSONDecodeError, TypeError):
                                recv_body = received

                        message_log.append({
                            "index": msg_idx,
                            "action": "receive",
                            "data": recv_body,
                        })

                        # 变量提取
                        for extraction in msg_cfg.get("extractions", []):
                            val = _jsonpath_extract(recv_body, extraction["expression"])
                            if val is not None:
                                context[extraction["variable"]] = val

                        # 断言
                        for assertion in msg_cfg.get("assertions", []):
                            passed, fail_msg = _assert_ws(assertion, recv_body)
                            if not passed:
                                step_status = RunStatus.failed
                                all_passed = False
                                error_msg = f"消息 #{msg_idx}: {fail_msg}"
                                break
                        if step_status == RunStatus.failed:
                            break

                    elif action == "disconnect":
                        message_log.append({"index": msg_idx, "action": "disconnect"})
                        break

            duration = int((time.monotonic() - step_start) * 1000)
            response_data = {
                "messages": message_log,
                "duration_ms": duration,
            }
            request_data["messages"] = [
                m for m in message_log if m.get("action") == "send"
            ]

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


def _assert_ws(assertion: dict, body) -> tuple[bool, str]:
    """WebSocket 消息断言"""
    target = assertion.get("target")
    operator = assertion.get("operator")
    expected = assertion.get("expected")
    expression = assertion.get("expression", "")

    actual = None
    if target == "body":
        actual = _jsonpath_extract(body, expression) if expression else body
    elif target == "raw":
        actual = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)

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
