"""gRPC 接口测试执行器

使用 grpc_tools.protoc 编译 .proto 为 descriptor set，
通过 descriptor_pool + message_factory 动态创建消息，
并根据 Proto 方法描述支持 Unary、Server Streaming、Client Streaming 和 Bidi Streaming。
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import PurePosixPath

import grpc
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.json_format import MessageToDict, Parse
from grpc_tools import protoc
from jsonpath_ng import parse as jp_parse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import publish_run_event
from app.services.dataset_execution import redact_execution_evidence
from app.services.execution_contract import assertion_result, extraction_result, response_contract
from app.models.case import RunStatus, StepResult, TestCase, TestRun


_MAX_TLS_ROOT_CERTIFICATE_BYTES = 1024 * 1024


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        return


def _grpc_mode(method_desc) -> str:
    """Return the RPC shape declared by the compiled Proto method."""

    client_streaming = bool(method_desc.client_streaming)
    server_streaming = bool(method_desc.server_streaming)
    if client_streaming and server_streaming:
        return "bidi_stream"
    if client_streaming:
        return "client_stream"
    if server_streaming:
        return "server_stream"
    return "unary"


def _parse_request_messages(request_json_str: str, req_class, client_streaming: bool) -> list:
    try:
        payload = json.loads(request_json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Request JSON 解析失败: {exc}") from exc

    if client_streaming:
        if not isinstance(payload, list) or not payload:
            raise ValueError("Client Streaming 请求必须是非空 JSON 数组")
        payloads = payload
    else:
        if not isinstance(payload, dict):
            raise ValueError("Unary/Server Streaming 请求必须是 JSON 对象")
        payloads = [payload]

    messages = []
    for index, item in enumerate(payloads):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index + 1} 个 gRPC 请求必须是 JSON 对象")
        messages.append(Parse(json.dumps(item), req_class()))
    return messages


async def _collect_stream(response_call, timeout: float) -> list:
    async def collect() -> list:
        return [response async for response in response_call]

    return await asyncio.wait_for(collect(), timeout=timeout + 5)


async def _invoke_grpc_call(
    channel,
    method_path: str,
    req_class,
    resp_class,
    request_messages: list,
    method_desc,
    timeout: float,
    metadata,
) -> list:
    """Invoke the RPC shape declared by ``method_desc`` and return response messages."""

    mode = _grpc_mode(method_desc)
    request_serializer = req_class.SerializeToString
    response_deserializer = resp_class.FromString

    if mode == "unary":
        call = channel.unary_unary(
            method_path,
            request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )
        response = await asyncio.wait_for(
            call(request_messages[0], timeout=timeout, metadata=metadata),
            timeout=timeout + 5,
        )
        return [response]

    if mode == "server_stream":
        call = channel.unary_stream(
            method_path,
            request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )
        response_call = call(request_messages[0], timeout=timeout, metadata=metadata)
        return await _collect_stream(response_call, timeout)

    async def request_iterator():
        for request_message in request_messages:
            yield request_message

    if mode == "client_stream":
        call = channel.stream_unary(
            method_path,
            request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )
        response = await asyncio.wait_for(
            call(request_iterator(), timeout=timeout, metadata=metadata),
            timeout=timeout + 5,
        )
        return [response]

    call = channel.stream_stream(
        method_path,
        request_serializer=request_serializer,
        response_deserializer=response_deserializer,
    )
    response_call = call(request_iterator(), timeout=timeout, metadata=metadata)
    return await _collect_stream(response_call, timeout)


def _response_body(response_messages: list, response_class, server_streaming: bool):
    values = [MessageToDict(message, preserving_proto_field_name=True) for message in response_messages]
    if server_streaming:
        return values
    if not values:
        return MessageToDict(response_class(), preserving_proto_field_name=True)
    return values[0]


_MAX_PROTO_FILES = 64
_MAX_PROTO_BUNDLE_BYTES = 8 * 1024 * 1024


def _safe_proto_path(name: str) -> str:
    """校验并规范化 import 文件名，禁止逃逸临时编译目录。"""
    normalized = str(name).replace("\\", "/")
    raw_parts = normalized.split("/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or ":" in normalized
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise RuntimeError(f"Proto import 文件名不安全: {name}")
    return str(path)


def _compile_proto(proto_content: str, proto_files: dict[str, str] | None = None) -> descriptor_pb2.FileDescriptorSet:
    """编译单文件或带 import 的 Proto 文件包为 FileDescriptorSet。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        proto_path = os.path.join(tmpdir, "service.proto")
        with open(proto_path, "w", encoding="utf-8") as f:
            f.write(proto_content)

        if proto_files is not None and not isinstance(proto_files, dict):
            raise RuntimeError("Proto import 文件包必须是对象")
        files = proto_files or {}
        auxiliary_files = [raw_name for raw_name in files if str(raw_name).replace("\\", "/") != "service.proto"]
        if len(auxiliary_files) + 1 > _MAX_PROTO_FILES:
            raise RuntimeError(f"Proto import 文件数不能超过 {_MAX_PROTO_FILES}")
        total_bytes = len(str(proto_content).encode("utf-8"))
        for raw_name, content in files.items():
            name = _safe_proto_path(raw_name)
            if not isinstance(content, str):
                raise RuntimeError(f"Proto import 文件内容无效: {raw_name}")
            total_bytes += len(content.encode("utf-8"))
            if total_bytes > _MAX_PROTO_BUNDLE_BYTES:
                raise RuntimeError(f"Proto 文件包不能超过 {_MAX_PROTO_BUNDLE_BYTES // (1024 * 1024)} MB")
            # proto_content remains the authoritative entry file. This also
            # avoids silently compiling stale duplicate content for service.proto.
            if name == "service.proto":
                continue
            file_path = os.path.join(tmpdir, *name.split("/"))
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        desc_path = os.path.join(tmpdir, "descriptor.bin")
        result = protoc.main(
            [
                "protoc",
                f"--proto_path={tmpdir}",
                f"--descriptor_set_out={desc_path}",
                "--include_imports",
                proto_path,
            ]
        )
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


def _grpc_tls_config(step: dict, context: dict) -> tuple[bytes | None, tuple[tuple[str, str], ...] | None, str | None]:
    """Build TLS inputs without allowing private keys into a case configuration."""

    raw_root_certificates = step.get("tls_root_certificates")
    root_certificates: bytes | None = None
    if raw_root_certificates is not None:
        if not isinstance(raw_root_certificates, str) or not raw_root_certificates.strip():
            raise ValueError("tls_root_certificates 必须是非空 PEM 字符串")
        if len(raw_root_certificates.encode("utf-8")) > _MAX_TLS_ROOT_CERTIFICATE_BYTES:
            raise ValueError("tls_root_certificates 不能超过 1 MiB")
        if "BEGIN CERTIFICATE" not in raw_root_certificates:
            raise ValueError("tls_root_certificates 必须包含 PEM 证书")
        if "PRIVATE KEY" in raw_root_certificates:
            raise ValueError("tls_root_certificates 不能包含私钥")
        root_certificates = raw_root_certificates.encode("utf-8")

    server_name = _render(str(step.get("tls_server_name") or ""), context).strip()
    if any(char in server_name for char in "\r\n"):
        raise ValueError("tls_server_name 无效")
    channel_options = (("grpc.ssl_target_name_override", server_name),) if server_name else None
    return root_certificates, channel_options, server_name or None


async def run_grpc_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict):
    cfg = case.config
    evidence_redact_fields = cfg.get("dataset_redact_fields") or []
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
        assertion_records: list[dict] = []
        extraction_records: list[dict] = []
        error_msg = None
        step_status = RunStatus.passed
        mode = "unary"

        try:
            target = _render(step.get("target", ""), context)
            use_tls = step.get("use_tls", False)
            tls_root_certificates = None
            tls_channel_options = None
            tls_server_name = None
            if use_tls:
                tls_root_certificates, tls_channel_options, tls_server_name = _grpc_tls_config(step, context)
            proto_content = step.get("proto_content", "")
            proto_files = step.get("proto_files")
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
                "tls_server_name": tls_server_name,
                "tls_root_certificate_configured": tls_root_certificates is not None,
            }

            # 编译 proto（在线程池中执行，避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            desc_set = await loop.run_in_executor(None, _compile_proto, proto_content, proto_files)
            pool = _build_pool(desc_set)

            # 查找 service → method → 输入/输出消息类型
            svc_desc = pool.FindServiceByName(service_name)
            method_desc = svc_desc.FindMethodByName(method_name)
            req_desc = pool.FindMessageTypeByName(method_desc.input_type.full_name)
            resp_desc = pool.FindMessageTypeByName(method_desc.output_type.full_name)

            ReqClass = message_factory.GetMessageClass(req_desc)
            RespClass = message_factory.GetMessageClass(resp_desc)

            mode = _grpc_mode(method_desc)
            request_data["grpc_mode"] = mode
            request_messages = _parse_request_messages(
                request_json_str,
                ReqClass,
                bool(method_desc.client_streaming),
            )

            # 构建 gRPC method path: /package.ServiceName/MethodName
            method_path = f"/{service_name}/{method_name}"

            # 建立 channel 并调用
            if use_tls:
                credentials = grpc.ssl_channel_credentials(root_certificates=tls_root_certificates)
                channel = grpc.aio.secure_channel(target, credentials, options=tls_channel_options)
            else:
                channel = grpc.aio.insecure_channel(target)

            try:
                md = list(metadata.items()) if metadata else None
                response_messages = await _invoke_grpc_call(
                    channel,
                    method_path,
                    ReqClass,
                    RespClass,
                    request_messages,
                    method_desc,
                    timeout,
                    md,
                )
            finally:
                await channel.close()

            duration = int((time.monotonic() - step_start) * 1000)

            # 响应转 dict
            resp_body = _response_body(
                response_messages,
                RespClass,
                bool(method_desc.server_streaming),
            )
            grpc_status = "OK"

            response_data = response_contract(
                "grpc",
                body=resp_body,
                duration_ms=duration,
                metadata={"grpc_status": grpc_status},
            )
            response_data["grpc_mode"] = mode
            response_data["grpc_status"] = grpc_status

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
            for assertion in step.get("assertions", []):
                passed, msg = _assert_grpc(assertion, resp_body, grpc_status, duration)
                assertion_records.append(assertion_result(assertion, passed=passed, message=msg))
                if not passed:
                    step_status = RunStatus.failed
                    all_passed = False
                    error_msg = msg
                    break
            response_data["assertions"] = assertion_records

        except grpc.aio.AioRpcError as e:
            duration = int((time.monotonic() - step_start) * 1000)
            grpc_status = e.code().name
            grpc_details = e.details() or ""
            response_data = response_contract(
                "grpc",
                body=None,
                duration_ms=duration,
                metadata={"grpc_status": grpc_status, "grpc_details": grpc_details},
            )
            response_data["grpc_mode"] = mode
            response_data["grpc_status"] = grpc_status
            response_data["grpc_details"] = grpc_details
            # 仍然尝试运行断言（用户可能断言 grpc_status == UNAVAILABLE 等）
            assertion_failed = False
            for assertion in step.get("assertions", []):
                passed, msg = _assert_grpc(assertion, None, grpc_status, duration)
                assertion_records.append(assertion_result(assertion, passed=passed, message=msg))
                if not passed:
                    assertion_failed = True
                    error_msg = msg
                    break
            response_data["assertions"] = assertion_records
            response_data["extractions"] = extraction_records
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
        persisted_request_data = redact_execution_evidence(request_data, evidence_redact_fields)
        persisted_response_data = redact_execution_evidence(response_data, evidence_redact_fields)
        step_result.request_data = persisted_request_data
        step_result.response_data = persisted_response_data
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
                    "request_data": persisted_request_data,
                    "response_data": persisted_response_data,
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
