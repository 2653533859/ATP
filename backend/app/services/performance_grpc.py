"""Dynamic Proto gRPC performance executor.

The performance worker runs synchronously inside a Celery event-loop thread.
This module therefore uses the thread-safe synchronous gRPC channel rather
than ``grpc.aio``.  Each load slot owns a loop of RPCs, while the coordinator
keeps cancellation and resource sampling responsive.
"""

from __future__ import annotations

import base64
from collections import Counter
from collections.abc import Mapping, Sequence
import json
import math
import re
import tempfile
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import grpc
from google.protobuf import descriptor_pb2, descriptor_pool, json_format, message_factory
from grpc_tools import protoc

from app.core import minio_client
from app.services.performance_process import PerformanceRunCancelled


class GrpcPerformanceOptionsError(ValueError):
    """Raised when gRPC performance options are unsafe or incomplete."""


_TARGET_RE = re.compile(r"^(?:\[[0-9a-fA-F:]+\]|[A-Za-z0-9.-]+)(?::\d{1,5})$")
_METADATA_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(-bin)?$")
_SENSITIVE_METADATA_RE = re.compile(
    r"(?:authorization|cookie|token|secret|password|api[-_]?key)",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")
_ALLOWED_MODES = {"unary", "server_stream", "client_stream", "bidi_stream"}


def target_hostname(target: object) -> str | None:
    """Return a normalized hostname from a gRPC target or URL."""
    raw = str(target or "").strip()
    if not raw:
        return None
    if "://" in raw:
        parsed = urlparse(raw)
        return parsed.hostname.lower() if parsed.hostname else None
    host = raw.rsplit(":", 1)[0]
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host.lower() if host else None


def validate_grpc_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the persisted gRPC load configuration."""
    if not isinstance(options, Mapping):
        raise GrpcPerformanceOptionsError("gRPC performance options must be a JSON object")

    raw_target = str(options.get("target") or "").strip()
    use_tls_from_scheme = raw_target.startswith(("grpcs://", "https://"))
    target = raw_target
    if "://" in target:
        parsed = urlparse(target)
        target = parsed.netloc
    if not _TARGET_RE.fullmatch(target):
        raise GrpcPerformanceOptionsError("gRPC target must be host:port, for example api.example.test:50051")
    port = int(target.rsplit(":", 1)[1])
    if not 1 <= port <= 65535:
        raise GrpcPerformanceOptionsError("gRPC target port must be between 1 and 65535")

    service = str(options.get("service") or "").strip().strip("/")
    method = str(options.get("method") or "").strip().strip("/")
    if not service or "." not in service or not method:
        raise GrpcPerformanceOptionsError("gRPC service must include its package and method is required")

    mode = str(options.get("mode") or "unary").strip().lower()
    if mode not in _ALLOWED_MODES:
        raise GrpcPerformanceOptionsError(f"Unsupported gRPC call mode: {mode}")

    request = options.get("request", {})
    if not isinstance(request, Mapping):
        raise GrpcPerformanceOptionsError("gRPC request must be a JSON object")
    raw_requests = options.get("requests")
    if raw_requests is None:
        requests = [dict(request)]
    elif isinstance(raw_requests, Sequence) and not isinstance(raw_requests, (str, bytes, bytearray)):
        requests = []
        for item in raw_requests:
            if not isinstance(item, Mapping):
                raise GrpcPerformanceOptionsError("gRPC requests must contain JSON objects")
            requests.append(dict(item))
        if not requests:
            raise GrpcPerformanceOptionsError("gRPC requests cannot be empty")
    else:
        raise GrpcPerformanceOptionsError("gRPC requests must be a JSON array")
    if mode in {"client_stream", "bidi_stream"} and not requests:
        raise GrpcPerformanceOptionsError("streaming gRPC calls require at least one request")

    metadata = _validate_metadata(options.get("metadata") or {})
    timeout = _positive_number(options.get("timeout_seconds", options.get("timeout", 30)), "timeout_seconds")
    if timeout > 300:
        raise GrpcPerformanceOptionsError("gRPC per-call timeout cannot exceed 300 seconds")

    concurrency = _positive_int(
        options.get("concurrency", options.get("users", options.get("vus", 1))),
        "concurrency",
    )
    if concurrency > 10000:
        raise GrpcPerformanceOptionsError("gRPC concurrency cannot exceed 10000")

    duration_seconds = _duration_seconds(
        options.get("duration_seconds", options.get("duration", options.get("run_time", 30)))
    )
    if duration_seconds <= 0:
        raise GrpcPerformanceOptionsError("gRPC duration must be greater than zero")

    iterations = options.get("iterations")
    normalized_iterations = None if iterations is None else _positive_int(iterations, "iterations")
    thresholds = options.get("thresholds", {})
    if thresholds is not None and not isinstance(thresholds, Mapping):
        raise GrpcPerformanceOptionsError("gRPC thresholds must be a JSON object")

    normalized: dict[str, Any] = {
        "target": target,
        "service": service,
        "method": method,
        "mode": mode,
        "request": dict(request),
        "requests": requests,
        "metadata": metadata,
        "timeout_seconds": timeout,
        "concurrency": concurrency,
        "duration_seconds": duration_seconds,
        "iterations": normalized_iterations,
        "thresholds": dict(thresholds or {}),
        "use_tls": bool(options.get("use_tls", use_tls_from_scheme)),
    }
    if "tls_root_certificates" in options and "tls_root_certificates_file" in options:
        raise GrpcPerformanceOptionsError("set only one of tls_root_certificates or tls_root_certificates_file")
    if "tls_root_certificates" in options:
        root_certificates = options.get("tls_root_certificates")
        if not isinstance(root_certificates, str) or not root_certificates.strip():
            raise GrpcPerformanceOptionsError("tls_root_certificates must be a non-empty PEM string")
        if len(root_certificates.encode("utf-8")) > 1024 * 1024:
            raise GrpcPerformanceOptionsError("tls_root_certificates cannot exceed 1 MiB")
        if "BEGIN CERTIFICATE" not in root_certificates:
            raise GrpcPerformanceOptionsError("tls_root_certificates must contain a PEM certificate")
        normalized["tls_root_certificates"] = root_certificates
    if "tls_root_certificates_file" in options:
        root_file = options.get("tls_root_certificates_file")
        if not isinstance(root_file, str) or not root_file.strip() or "\n" in root_file or "\r" in root_file:
            raise GrpcPerformanceOptionsError("tls_root_certificates_file must be a valid path")
        if not root_file.startswith("/"):
            raise GrpcPerformanceOptionsError("tls_root_certificates_file must be an absolute worker path")
        if len(root_file) > 1024:
            raise GrpcPerformanceOptionsError("tls_root_certificates_file path is too long")
        normalized["tls_root_certificates_file"] = root_file
    if "tls_server_name" in options:
        server_name = str(options["tls_server_name"]).strip()
        if not server_name or any(char in server_name for char in "\r\n"):
            raise GrpcPerformanceOptionsError("tls_server_name is invalid")
        normalized["tls_server_name"] = server_name
    return normalized


def compile_grpc_proto(proto_content: str) -> descriptor_pb2.FileDescriptorSet:
    """Compile Proto text into a descriptor set without generating source files."""
    if not isinstance(proto_content, str) or not proto_content.strip():
        raise GrpcPerformanceOptionsError("Proto definition cannot be empty")
    with tempfile.TemporaryDirectory(prefix="atp-grpc-proto-") as tmpdir:
        tmp_path = Path(tmpdir)
        proto_path = tmp_path / "service.proto"
        descriptor_path = tmp_path / "descriptor.bin"
        proto_path.write_text(proto_content, encoding="utf-8")
        result = protoc.main(
            [
                "protoc",
                f"--proto_path={tmp_path}",
                f"--descriptor_set_out={descriptor_path}",
                "--include_imports",
                str(proto_path),
            ]
        )
        if result != 0 or not descriptor_path.exists():
            raise GrpcPerformanceOptionsError("Proto compilation failed; check syntax and imports")
        return descriptor_pb2.FileDescriptorSet.FromString(descriptor_path.read_bytes())


def _build_pool(descriptor_set: descriptor_pb2.FileDescriptorSet) -> descriptor_pool.DescriptorPool:
    pool = descriptor_pool.DescriptorPool()
    for file_proto in descriptor_set.file:
        pool.Add(file_proto)
    return pool


def _resolve_method(pool: descriptor_pool.DescriptorPool, service: str, method: str):
    try:
        service_descriptor = pool.FindServiceByName(service)
        method_descriptor = service_descriptor.FindMethodByName(method)
    except KeyError as exc:
        raise GrpcPerformanceOptionsError(f"Proto service or method not found: {service}/{method}") from exc
    if method_descriptor is None:
        raise GrpcPerformanceOptionsError(f"Proto method not found: {service}/{method}")
    return method_descriptor


def _message_class(descriptor):
    return message_factory.GetMessageClass(descriptor)


def summarize_grpc_samples(
    latencies_ms: Sequence[float | int],
    *,
    failures: int = 0,
    duration_ms: int | float | None = None,
    total_requests: int | None = None,
    statuses: Mapping[str, int] | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Map gRPC call samples to the common performance summary contract."""
    samples = [float(value) for value in latencies_ms if isinstance(value, (int, float)) and value >= 0]
    requests = max(total_requests or 0, len(samples), failures)
    duration_seconds = float(duration_ms or 0) / 1000
    metrics: dict[str, object] = {
        "rps": requests / duration_seconds if requests and duration_seconds > 0 else None,
        "p95_ms": _percentile(samples, 0.95),
        "p99_ms": _percentile(samples, 0.99),
        "error_rate": failures / requests if requests else None,
    }
    return {
        "executor": "grpc",
        **metrics,
        "iterations": requests,
        "data_received": None,
        "data_sent": None,
        "grpc_statuses": dict(statuses or {}),
        "thresholds": _evaluate_thresholds(metrics, thresholds),
    }


def run_grpc_script(
    *,
    run_id: int,
    script_object_name: str,
    options: dict | None = None,
    timeout_seconds: int = 1800,
    cancel_check: Callable[[], bool] | None = None,
    metric_callback: Callable[[], None] | None = None,
    metric_interval_seconds: float = 5.0,
    max_metric_samples: int = 7200,
) -> tuple[dict[str, Any], str, int]:
    """Execute unary or streaming gRPC calls concurrently and persist a summary."""
    normalized = validate_grpc_options(options if isinstance(options, Mapping) else {})
    env = _environment_values(options)
    rendered_requests = [_render_json_values(item, env) for item in normalized["requests"]]
    rendered_metadata = _metadata_items(normalized["metadata"], env)

    with tempfile.TemporaryDirectory(prefix=f"atp-grpc-{run_id}-") as tmpdir:
        tmp_path = Path(tmpdir)
        proto_path = tmp_path / "service.proto"
        minio_client.download_file(script_object_name, proto_path)
        descriptor_set = compile_grpc_proto(proto_path.read_text(encoding="utf-8"))
        pool = _build_pool(descriptor_set)
        method_descriptor = _resolve_method(pool, normalized["service"], normalized["method"])
        request_class = _message_class(method_descriptor.input_type)
        response_class = _message_class(method_descriptor.output_type)
        request_bytes = _serialize_requests(request_class, rendered_requests)
        method_path = f"/{normalized['service']}/{normalized['method']}"

        channel = _create_channel(normalized)
        call = _create_call(channel, method_path, request_class, response_class, normalized["mode"])
        stats = _GrpcStats()
        stop_event = threading.Event()
        futures: list[Future[None]] = []
        started = time.monotonic()
        executor = ThreadPoolExecutor(max_workers=normalized["concurrency"], thread_name_prefix="atp-grpc")
        worker_errors: list[str] = []
        try:
            futures = [
                executor.submit(
                    _run_grpc_slot,
                    call,
                    normalized,
                    request_class,
                    request_bytes,
                    rendered_metadata,
                    stats,
                    stop_event,
                )
                for _ in range(normalized["concurrency"])
            ]
            next_metric_at = started
            while True:
                done, _ = wait(futures, timeout=0.1)
                for future in done:
                    if future in futures:
                        futures.remove(future)
                    try:
                        future.result()
                    except Exception as exc:
                        worker_errors.append(str(exc)[:500])
                        stop_event.set()
                if worker_errors:
                    raise RuntimeError(worker_errors[0])
                now = time.monotonic()
                if metric_callback is not None and stats.metric_samples < max_metric_samples and now >= next_metric_at:
                    try:
                        metric_callback()
                    except Exception:
                        pass
                    stats.metric_samples += 1
                    next_metric_at = now + max(0.5, metric_interval_seconds)
                if cancel_check is not None and cancel_check():
                    raise PerformanceRunCancelled("Performance run cancelled by user")
                if normalized["iterations"] is None and now - started >= normalized["duration_seconds"]:
                    stop_event.set()
                    channel.close()
                if not futures:
                    break
                if normalized["iterations"] is not None and stats.total >= normalized["iterations"]:
                    stop_event.set()
                    channel.close()
        finally:
            stop_event.set()
            channel.close()
            for future in futures:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)

        duration_ms = int((time.monotonic() - started) * 1000)
        summary = summarize_grpc_samples(
            stats.latencies_ms,
            failures=stats.failures,
            duration_ms=duration_ms,
            total_requests=stats.total,
            statuses=stats.statuses,
            thresholds=normalized["thresholds"],
        )
        summary.update(
            {
                "grpc_mode": normalized["mode"],
                "grpc_service": normalized["service"],
                "grpc_method": normalized["method"],
                "grpc_responses": stats.responses,
                "exit_code": 0 if stats.total > 0 and not stats.failures else 1,
            }
        )
        if stats.failures:
            summary["grpc_error"] = ", ".join(
                f"{status}={count}" for status, count in sorted(stats.statuses.items()) if status != "OK"
            )[:1000]

        result_path = tmp_path / "summary.json"
        result_path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        object_name = f"performance/runs/{run_id}/summary.json"
        minio_client.upload_file(object_name, result_path, content_type="application/json")
        return summary, object_name, duration_ms


class _GrpcStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.latencies_ms: list[float] = []
        self.statuses: Counter[str] = Counter()
        self.total = 0
        self.started = 0
        self.failures = 0
        self.responses = 0
        self.metric_samples = 0

    def reserve(self, request_count: int, target_iterations: object) -> int | None:
        with self._lock:
            if target_iterations is not None and self.started >= _coerce_int(target_iterations, "iterations"):
                return None
            request_index = self.started % request_count
            self.started += 1
            return request_index

    def record(self, latency_ms: float, status: str, failed: bool, response_count: int) -> None:
        with self._lock:
            self.latencies_ms.append(latency_ms)
            self.statuses[status] += 1
            self.total += 1
            self.failures += int(failed)
            self.responses += response_count


def _run_grpc_slot(
    call: Any,
    options: Mapping[str, Any],
    request_class: Any,
    request_bytes: list[bytes],
    metadata: list[tuple[str, str | bytes]],
    stats: _GrpcStats,
    stop_event: threading.Event,
) -> None:
    deadline = time.monotonic() + float(options["duration_seconds"])
    target_iterations = options.get("iterations")
    while not stop_event.is_set():
        if target_iterations is None and time.monotonic() >= deadline:
            return
        request_index = stats.reserve(len(request_bytes), target_iterations)
        if request_index is None:
            return
        request_payload = request_bytes[request_index]
        started = time.monotonic()
        status = "OK"
        failed = False
        response_count = 0
        try:
            response = _invoke_call(
                call,
                request_class,
                options["mode"],
                request_payload,
                request_bytes,
                metadata,
                options,
            )
            if isinstance(response, int):
                response_count = response
            else:
                response_count = 1
        except grpc.RpcError as exc:
            code = exc.code()
            # Closing the channel at a normal duration boundary cancels only the
            # in-flight tail; it is not an application failure. User cancellation
            # never reaches summary generation because the coordinator raises.
            if stop_event.is_set() and code == grpc.StatusCode.CANCELLED:
                return
            status = code.name if code is not None else "UNKNOWN"
            failed = True
        except Exception:
            status = "INTERNAL"
            failed = True
        stats.record((time.monotonic() - started) * 1000, status, failed, response_count)


def _invoke_call(
    call: Any,
    request_class: Any,
    mode: str,
    request_payload: bytes,
    request_bytes: list[bytes],
    metadata: list[tuple[str, str | bytes]],
    options: Mapping[str, Any],
) -> int:
    request = request_class.FromString(request_payload)
    timeout = float(options["timeout_seconds"])
    if mode == "unary":
        call(request, timeout=timeout, metadata=metadata)
        return 1
    if mode == "server_stream":
        response_count = 0
        for _ in call(request, timeout=timeout, metadata=metadata):
            response_count += 1
        return response_count
    requests = (request_class.FromString(payload) for payload in request_bytes)
    if mode == "client_stream":
        call(requests, timeout=timeout, metadata=metadata)
        return 1
    response_count = 0
    for _ in call(requests, timeout=timeout, metadata=metadata):
        response_count += 1
    return response_count


def _create_call(channel: Any, method_path: str, request_class: Any, response_class: Any, mode: str):
    request_serializer = lambda message: message.SerializeToString()
    response_deserializer = response_class.FromString
    if mode == "unary":
        return channel.unary_unary(
            method_path,
            request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )
    if mode == "server_stream":
        return channel.unary_stream(
            method_path,
            request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )
    if mode == "client_stream":
        return channel.stream_unary(
            method_path,
            request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )
    return channel.stream_stream(
        method_path,
        request_serializer=request_serializer,
        response_deserializer=response_deserializer,
    )


def _create_channel(options: Mapping[str, Any]):
    if not options["use_tls"]:
        return grpc.insecure_channel(options["target"])
    channel_options: list[tuple[str, str]] = []
    if options.get("tls_server_name"):
        channel_options.append(("grpc.ssl_target_name_override", str(options["tls_server_name"])))
    root_certificates = options.get("tls_root_certificates")
    root_file = options.get("tls_root_certificates_file")
    if root_certificates is not None and root_file is not None:
        raise GrpcPerformanceOptionsError("set only one of tls_root_certificates or tls_root_certificates_file")
    root_bytes: bytes | None
    if root_file is not None:
        try:
            root_bytes = Path(str(root_file)).read_bytes()
        except OSError as exc:
            raise GrpcPerformanceOptionsError(f"cannot read gRPC root certificate file: {root_file}") from exc
    else:
        root_bytes = root_certificates.encode("utf-8") if isinstance(root_certificates, str) else None
    if root_bytes is not None and b"BEGIN CERTIFICATE" not in root_bytes:
        raise GrpcPerformanceOptionsError("gRPC root certificates must contain a PEM certificate")
    credentials = grpc.ssl_channel_credentials(root_certificates=root_bytes)
    return grpc.secure_channel(options["target"], credentials, options=channel_options)


def _serialize_requests(request_class, requests: Sequence[Mapping[str, Any]]) -> list[bytes]:
    result: list[bytes] = []
    for payload in requests:
        try:
            message = json_format.ParseDict(dict(payload), request_class(), ignore_unknown_fields=False)
        except (TypeError, ValueError) as exc:
            raise GrpcPerformanceOptionsError(f"gRPC request does not match the Proto message: {exc}") from exc
        result.append(message.SerializeToString())
    return result


def _environment_values(options: Mapping[str, Any] | None) -> dict[str, str]:
    value = options.get("env") if isinstance(options, Mapping) else None
    return {str(key): str(item) for key, item in value.items()} if isinstance(value, Mapping) else {}


def _render_json_values(value: Any, env: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {key: _render_json_values(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [_render_json_values(item, env) for item in value]
    if isinstance(value, str):
        return _PLACEHOLDER_RE.sub(lambda match: env.get(match.group(1), match.group(0)), value)
    return value


def _metadata_items(metadata: Mapping[str, str], env: Mapping[str, str]) -> list[tuple[str, str | bytes]]:
    result: list[tuple[str, str | bytes]] = []
    for key, value in metadata.items():
        rendered = _render_json_values(value, env)
        if key.endswith("-bin"):
            result.append((key, base64.b64decode(str(rendered), validate=True)))
        else:
            result.append((key, str(rendered)))
    return result


def _validate_metadata(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise GrpcPerformanceOptionsError("gRPC metadata must be a JSON object")
    result: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip().lower()
        if not _METADATA_KEY_RE.fullmatch(key):
            raise GrpcPerformanceOptionsError(f"Invalid gRPC metadata key: {raw_key}")
        if _SENSITIVE_METADATA_RE.search(key) and not _is_env_reference(raw_value):
            raise GrpcPerformanceOptionsError(f"敏感 metadata {key} 必须引用环境变量")
        rendered = str(raw_value)
        if any(char in rendered for char in "\r\n"):
            raise GrpcPerformanceOptionsError(f"gRPC metadata {key} cannot contain a newline")
        if key.endswith("-bin"):
            try:
                base64.b64decode(rendered, validate=True)
            except Exception as exc:
                raise GrpcPerformanceOptionsError(f"Binary metadata {key} must be Base64") from exc
        result[key] = rendered
    return result


def _is_env_reference(value: object) -> bool:
    rendered = str(value).strip()
    return bool(re.fullmatch(r"\{\{[A-Za-z_][A-Za-z0-9_]*\}\}", rendered))


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise GrpcPerformanceOptionsError(f"{field} must be a positive integer")
    if not isinstance(value, (int, float, str)):
        raise GrpcPerformanceOptionsError(f"{field} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise GrpcPerformanceOptionsError(f"{field} must be a positive integer") from exc
    if number <= 0:
        raise GrpcPerformanceOptionsError(f"{field} must be a positive integer")
    return number


def _positive_number(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise GrpcPerformanceOptionsError(f"{field} must be positive")
    if not isinstance(value, (int, float, str)):
        raise GrpcPerformanceOptionsError(f"{field} must be positive")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GrpcPerformanceOptionsError(f"{field} must be positive") from exc
    if not math.isfinite(number) or number <= 0:
        raise GrpcPerformanceOptionsError(f"{field} must be positive")
    return number


def _coerce_int(value: object, field: str) -> int:
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        raise GrpcPerformanceOptionsError(f"{field} must be a positive integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise GrpcPerformanceOptionsError(f"{field} must be a positive integer") from exc


def _duration_seconds(value: object) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _positive_number(value, "duration_seconds")
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)?\s*", value, re.IGNORECASE)
        if match:
            amount = float(match.group(1))
            multiplier = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}.get((match.group(2) or "s").lower(), 1)
            return _positive_number(amount * multiplier, "duration_seconds")
    raise GrpcPerformanceOptionsError("duration_seconds must be a positive number or duration string")


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _evaluate_thresholds(metrics: Mapping[str, object], thresholds: object) -> dict[str, dict[str, dict[str, bool]]]:
    if not isinstance(thresholds, Mapping):
        return {}
    result: dict[str, dict[str, dict[str, bool]]] = {}
    for metric_name, rules in thresholds.items():
        value = metrics.get(str(metric_name))
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        raw_rules = [rules] if isinstance(rules, str) else rules
        if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes, bytearray)):
            continue
        metric_result: dict[str, dict[str, bool]] = {}
        for raw_rule in raw_rules:
            match = re.fullmatch(r"\s*(<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)\s*", str(raw_rule))
            if not match:
                continue
            operator, expected_text = match.groups()
            expected = float(expected_text)
            ok = {
                "<": value < expected,
                "<=": value <= expected,
                ">": value > expected,
                ">=": value >= expected,
            }[operator]
            metric_result[str(raw_rule)] = {"ok": ok}
        if metric_result:
            result[str(metric_name)] = metric_result
    return result
