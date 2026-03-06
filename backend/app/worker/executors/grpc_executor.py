"""gRPC 接口测试执行器

使用 grpc_tools.protoc 编译 .proto 为 descriptor set，
通过 descriptor_pool + message_factory 动态创建消息，
channel.unary_unary() 低级 API 执行调用。
"""
import asyncio
import json
import os
import tempfile
import time

import grpc
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.json_format import MessageToDict, Parse
from grpc_tools import protoc
from jsonpath_ng import parse as jp_parse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import publish_run_event
from app.models.case import RunStatus, StepResult, TestCase, TestRun


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        return


def _compile_proto(proto_content: str) -> descriptor_pb2.FileDescriptorSet:
    """编译 proto 内容为 FileDescriptorSet（纯描述符，不生成 Python 代码）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        proto_path = os.path.join(tmpdir, "service.proto")
        with open(proto_path, "w", encoding="utf-8") as f:
            f.write(proto_content)

        desc_path = os.path.join(tmpdir, "descriptor.bin")
        result = protoc.main([
            "protoc",
            f"--proto_path={tmpdir}",
            f"--descriptor_set_out={desc_path}",
            "--include_imports",
            proto_path,
        ])
        if result != 0:
            raise RuntimeError("Proto 编译失败，请检查 .proto 语法")

        with open(desc_path, "rb") as f:
            return descriptor_pb2.FileDescriptorSet.FromString(f.read())


def _build_pool(desc_set: descriptor_pb2.FileDescriptorSet) -> descriptor_pool.DescriptorPool:
    """从 FileDescriptorSet 构建独立的 DescriptorPool"""
    pool = descriptor_pool.DescriptorPool()
    for file_proto in desc_set.file:
        pool.Add(file_proto)
    return pool


async def run_grpc_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict):
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
            target = _render(step.get("target", ""), context)
            use_tls = step.get("use_tls", False)
            proto_content = step.get("proto_content", "")
            service_name = _render(step.get("service", ""), context)
            method_name = _render(step.get("method", ""), context)
            request_json_str = _render(step.get("request_json", "{}"), context)
            timeout = step.get("timeout", 30)
            metadata_cfg = step.get("metadata", {})

            # 渲染 metadata
            metadata = {}
            for k, v in metadata_cfg.items():
                metadata[k] = _render(v, context)

            request_data = {
                "target": target,
                "service": service_name,
                "method": method_name,
                "request_json": request_json_str,
                "metadata": metadata,
                "use_tls": use_tls,
            }

            # 解析请求 JSON
            try:
                req_dict = json.loads(request_json_str)
            except json.JSONDecodeError as e:
                raise ValueError(f"Request JSON 解析失败: {e}")

            # 编译 proto（在线程池中执行，避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            desc_set = await loop.run_in_executor(None, _compile_proto, proto_content)
            pool = _build_pool(desc_set)

            # 查找 service → method → 输入/输出消息类型
            svc_desc = pool.FindServiceByName(service_name)
            method_desc = svc_desc.FindMethodByName(method_name)
            req_desc = pool.FindMessageTypeByName(method_desc.input_type.full_name)
            resp_desc = pool.FindMessageTypeByName(method_desc.output_type.full_name)

            ReqClass = message_factory.GetPrototype(req_desc)
            RespClass = message_factory.GetPrototype(resp_desc)

            # 构造请求消息
            request_msg = Parse(json.dumps(req_dict), ReqClass())

            # 构建 gRPC method path: /package.ServiceName/MethodName
            method_path = f"/{service_name}/{method_name}"

            # 建立 channel 并调用
            if use_tls:
                channel = grpc.aio.secure_channel(target, grpc.ssl_channel_credentials())
            else:
                channel = grpc.aio.insecure_channel(target)

            try:
                call = channel.unary_unary(
                    method_path,
                    request_serializer=ReqClass.SerializeToString,
                    response_deserializer=RespClass.FromString,
                )
                md = list(metadata.items()) if metadata else None
                response_msg = await asyncio.wait_for(
                    call(request_msg, timeout=timeout, metadata=md),
                    timeout=timeout + 5,
                )
            finally:
                await channel.close()

            duration = int((time.monotonic() - step_start) * 1000)

            # 响应转 dict
            resp_body = MessageToDict(
                response_msg, preserving_proto_field_name=True,
            )
            grpc_status = "OK"

            response_data = {
                "grpc_status": grpc_status,
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
                passed, msg = _assert_grpc(assertion, resp_body, grpc_status, duration)
                if not passed:
                    step_status = RunStatus.failed
                    all_passed = False
                    error_msg = msg
                    break

        except grpc.aio.AioRpcError as e:
            duration = int((time.monotonic() - step_start) * 1000)
            grpc_status = e.code().name
            grpc_details = e.details() or ""
            response_data = {
                "grpc_status": grpc_status,
                "grpc_details": grpc_details,
                "body": None,
                "duration_ms": duration,
            }
            # 仍然尝试运行断言（用户可能断言 grpc_status == UNAVAILABLE 等）
            assertion_failed = False
            for assertion in step.get("assertions", []):
                passed, msg = _assert_grpc(assertion, None, grpc_status, duration)
                if not passed:
                    assertion_failed = True
                    error_msg = msg
                    break
            if assertion_failed:
                step_status = RunStatus.failed
                all_passed = False
            else:
                # 如果有断言且全部通过，不标记为 error
                if step.get("assertions"):
                    step_status = RunStatus.passed
                else:
                    step_status = RunStatus.error
                    all_passed = False
                    error_msg = f"gRPC 错误 [{grpc_status}]: {grpc_details}"

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


# ── 辅助函数 ───────────────────────────────────────────

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


def _assert_grpc(assertion: dict, body, grpc_status: str, duration_ms: int) -> tuple[bool, str]:
    """gRPC 响应断言"""
    target = assertion.get("target")
    operator = assertion.get("operator")
    expected = assertion.get("expected")
    expression = assertion.get("expression", "")

    actual = None
    if target == "body":
        if body is None:
            actual = None
        else:
            actual = _jsonpath_extract(body, expression) if expression else body
    elif target == "grpc_status":
        actual = grpc_status
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
