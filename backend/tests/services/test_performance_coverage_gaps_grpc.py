"""补齐 backend/app/services/performance_grpc.py 剩余未覆盖分支的单元测试。

针对 coverage.xml 中 hits=0 的路径：target 归一化、validate 的各类拒绝分支、
protoc 编译失败、服务/方法解析失败、协调器（worker 异常 / 时长与迭代上限 /
metric 回调吞异常）、channel 的 TLS 变体、序列化失败，以及 metadata、数值、
百分位与阈值评估等纯函数分支。

协调器测试统一把 `_run_grpc_slot` 换成假实现隔离真实网络；Proto 由进程内
grpc_tools.protoc 编译（无子进程、无网络）；MinIO 通过 monkeypatch 读写临时目录。
"""

from __future__ import annotations

import base64
import sys
import threading
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import performance_grpc
from app.services.performance_grpc import GrpcPerformanceOptionsError

PROTO = """
syntax = "proto3";
package atp.perf;

message EchoRequest { string message = 1; }
message EchoReply { string message = 1; }

service Echo {
  rpc Call(EchoRequest) returns (EchoReply);
}
"""


def _valid_options(**overrides):
    values = {
        "target": "127.0.0.1:50051",
        "service": "atp.perf.Echo",
        "method": "Call",
        "request": {"message": "hi"},
        "duration_seconds": "1ms",
    }
    values.update(overrides)
    return values


def _install_minio(monkeypatch) -> list[tuple[str, str, str | None]]:
    uploaded: list[tuple[str, str, str | None]] = []

    def download(_object_name, path):
        path.write_text(PROTO, encoding="utf-8")

    def upload(object_name, path, *, content_type=None):
        uploaded.append((object_name, path.read_text(encoding="utf-8"), content_type))

    monkeypatch.setattr(performance_grpc.minio_client, "download_file", download, raising=False)
    monkeypatch.setattr(performance_grpc.minio_client, "upload_file", upload, raising=False)
    return uploaded


def _fake_grpc(captured: dict):
    def ssl_channel_credentials(root_certificates=None):
        captured["root_certificates"] = root_certificates
        return "fake-credentials"

    def secure_channel(target, credentials, options=None):
        captured["tls_target"] = target
        captured["credentials"] = credentials
        captured["options"] = options
        return "tls-channel"

    def insecure_channel(target):
        captured["plain_target"] = target
        return "plain-channel"

    return types.SimpleNamespace(
        ssl_channel_credentials=ssl_channel_credentials,
        secure_channel=secure_channel,
        insecure_channel=insecure_channel,
    )


def test_target_hostname_normalizes_all_shapes():
    assert performance_grpc.target_hostname("") is None
    assert performance_grpc.target_hostname("grpcs://API.Example.test:443/load") == "api.example.test"
    assert performance_grpc.target_hostname("[2001:db8::1]:50051") == "2001:db8::1"
    assert performance_grpc.target_hostname("API.Example.test:50051") == "api.example.test"


def test_validate_grpc_options_rejects_non_mapping():
    with pytest.raises(GrpcPerformanceOptionsError, match="must be a JSON object"):
        performance_grpc.validate_grpc_options(["not-a-mapping"])


def test_validate_grpc_options_rejects_out_of_range_ports():
    for target in ("api.example.test:70000", "api.example.test:0"):
        with pytest.raises(GrpcPerformanceOptionsError, match="between 1 and 65535"):
            performance_grpc.validate_grpc_options(_valid_options(target=target))


def test_validate_grpc_options_requires_packaged_service_and_supported_mode():
    with pytest.raises(GrpcPerformanceOptionsError, match="include its package"):
        performance_grpc.validate_grpc_options(_valid_options(service="Echo"))
    with pytest.raises(GrpcPerformanceOptionsError, match="Unsupported gRPC call mode"):
        performance_grpc.validate_grpc_options(_valid_options(mode="stream"))


def test_validate_grpc_options_rejects_bad_request_shapes():
    with pytest.raises(GrpcPerformanceOptionsError, match="request must be a JSON object"):
        performance_grpc.validate_grpc_options(_valid_options(request=[1, 2]))
    with pytest.raises(GrpcPerformanceOptionsError, match="must contain JSON objects"):
        performance_grpc.validate_grpc_options(_valid_options(requests=[1, 2]))
    with pytest.raises(GrpcPerformanceOptionsError, match="cannot be empty"):
        performance_grpc.validate_grpc_options(_valid_options(requests=[]))
    with pytest.raises(GrpcPerformanceOptionsError, match="must be a JSON array"):
        performance_grpc.validate_grpc_options(_valid_options(requests=123))


def test_validate_grpc_options_enforces_timeout_and_concurrency_caps():
    with pytest.raises(GrpcPerformanceOptionsError, match="cannot exceed 300"):
        performance_grpc.validate_grpc_options(_valid_options(timeout_seconds=400))
    with pytest.raises(GrpcPerformanceOptionsError, match="cannot exceed 10000"):
        performance_grpc.validate_grpc_options(_valid_options(concurrency=20000))


def test_validate_grpc_options_rejects_non_mapping_thresholds():
    with pytest.raises(GrpcPerformanceOptionsError, match="thresholds must be a JSON object"):
        performance_grpc.validate_grpc_options(_valid_options(thresholds=[">1"]))


def test_validate_grpc_options_rejects_inline_certificates():
    with pytest.raises(GrpcPerformanceOptionsError, match="only one of"):
        performance_grpc.validate_grpc_options(
            _valid_options(
                tls_root_certificates="-----BEGIN CERTIFICATE-----",
                tls_root_certificates_file="/etc/ssl/ca.pem",
            )
        )
    with pytest.raises(GrpcPerformanceOptionsError, match="non-empty PEM string"):
        performance_grpc.validate_grpc_options(_valid_options(tls_root_certificates="   "))
    with pytest.raises(GrpcPerformanceOptionsError, match="cannot exceed 1 MiB"):
        performance_grpc.validate_grpc_options(_valid_options(tls_root_certificates="x" * (1024 * 1024 + 8)))
    with pytest.raises(GrpcPerformanceOptionsError, match="must contain a PEM certificate"):
        performance_grpc.validate_grpc_options(_valid_options(tls_root_certificates="cert-data"))


def test_validate_grpc_options_rejects_certificate_file_paths():
    with pytest.raises(GrpcPerformanceOptionsError, match="must be a valid path"):
        performance_grpc.validate_grpc_options(_valid_options(tls_root_certificates_file="  "))
    with pytest.raises(GrpcPerformanceOptionsError, match="absolute worker path"):
        performance_grpc.validate_grpc_options(_valid_options(tls_root_certificates_file="relative/ca.pem"))
    with pytest.raises(GrpcPerformanceOptionsError, match="path is too long"):
        performance_grpc.validate_grpc_options(_valid_options(tls_root_certificates_file="/" + "a" * 1100))


def test_validate_grpc_options_normalizes_server_name_and_rejects_controls():
    normalized = performance_grpc.validate_grpc_options(
        _valid_options(use_tls=True, tls_server_name="grpc.override.test")
    )
    assert normalized["tls_server_name"] == "grpc.override.test"
    with pytest.raises(GrpcPerformanceOptionsError, match="tls_server_name is invalid"):
        performance_grpc.validate_grpc_options(_valid_options(use_tls=True, tls_server_name="bad\r\nname"))
    with pytest.raises(GrpcPerformanceOptionsError, match="tls_server_name is invalid"):
        performance_grpc.validate_grpc_options(_valid_options(use_tls=True, tls_server_name="   "))


def test_compile_grpc_proto_rejects_empty_and_broken_definitions():
    with pytest.raises(GrpcPerformanceOptionsError, match="cannot be empty"):
        performance_grpc.compile_grpc_proto("   ")
    with pytest.raises(GrpcPerformanceOptionsError, match="Proto compilation failed"):
        performance_grpc.compile_grpc_proto("this is not a proto definition")


def test_resolve_method_reports_missing_service_and_method():
    class _MissingServicePool:
        def FindServiceByName(self, name):
            raise KeyError(name)

    class _MissingMethodService:
        def FindMethodByName(self, name):
            return None

    class _MissingMethodPool:
        def FindServiceByName(self, name):
            return _MissingMethodService()

    with pytest.raises(GrpcPerformanceOptionsError, match="service or method not found"):
        performance_grpc._resolve_method(_MissingServicePool(), "atp.perf.Echo", "Call")
    with pytest.raises(GrpcPerformanceOptionsError, match="Proto method not found"):
        performance_grpc._resolve_method(_MissingMethodPool(), "atp.perf.Echo", "Call")


def test_serialize_requests_reports_proto_mismatch():
    class _ExplodingRequestClass:
        def __init__(self):
            raise ValueError("unknown field")

    with pytest.raises(GrpcPerformanceOptionsError, match="does not match the Proto message"):
        performance_grpc._serialize_requests(_ExplodingRequestClass, [{"message": "hi"}])


def test_render_json_values_expands_templates_recursively():
    rendered = performance_grpc._render_json_values(
        {"items": ["{{TOKEN}}", 1], "nested": {"raw": "{{MISSING}}"}, "plain": "text"},
        {"TOKEN": "secret"},
    )
    assert rendered["items"] == ["secret", 1]
    assert rendered["nested"] == {"raw": "{{MISSING}}"}
    assert rendered["plain"] == "text"


def test_metadata_items_encodes_binary_and_renders_placeholders():
    binary = base64.b64encode(b"payload").decode()
    items = performance_grpc._metadata_items({"x-token": "{{TOKEN}}", "trace-bin": binary}, {"TOKEN": "abc"})
    assert items == [("x-token", "abc"), ("trace-bin", b"payload")]


def test_validate_metadata_rejects_bad_keys_values_and_binary():
    with pytest.raises(GrpcPerformanceOptionsError, match="metadata must be a JSON object"):
        performance_grpc._validate_metadata("nope")
    with pytest.raises(GrpcPerformanceOptionsError, match="Invalid gRPC metadata key"):
        performance_grpc._validate_metadata({"Bad Key": "x"})
    with pytest.raises(GrpcPerformanceOptionsError, match="cannot contain a newline"):
        performance_grpc._validate_metadata({"x-tag": "a\nb"})
    with pytest.raises(GrpcPerformanceOptionsError, match="must be Base64"):
        performance_grpc._validate_metadata({"trace-bin": "!!!"})


def test_positive_int_rejects_bool_non_scalar_junk_and_zero():
    for bad in (True, None, "abc", 0, -3):
        with pytest.raises(GrpcPerformanceOptionsError, match="must be a positive integer"):
            performance_grpc._positive_int(bad, "concurrency")
    assert performance_grpc._positive_int("7", "concurrency") == 7


def test_positive_number_rejects_bool_non_scalar_junk_and_nonfinite():
    for bad in (True, None, "abc", "inf", 0, -1):
        with pytest.raises(GrpcPerformanceOptionsError, match="must be positive"):
            performance_grpc._positive_number(bad, "timeout_seconds")
    assert performance_grpc._positive_number("2.5", "timeout_seconds") == 2.5


def test_coerce_int_rejects_junk_and_bool():
    for bad in (True, None, "abc"):
        with pytest.raises(GrpcPerformanceOptionsError, match="must be a positive integer"):
            performance_grpc._coerce_int(bad, "iterations")
    assert performance_grpc._coerce_int("3", "iterations") == 3


def test_duration_seconds_parses_suffixes_and_rejects_junk():
    assert performance_grpc._duration_seconds("250ms") == 0.25
    assert performance_grpc._duration_seconds("1.5m") == 90.0
    with pytest.raises(GrpcPerformanceOptionsError, match="duration_seconds"):
        performance_grpc._duration_seconds("not-a-duration")


def test_percentile_handles_empty_and_interpolated_inputs():
    assert performance_grpc._percentile([], 0.95) is None
    assert performance_grpc._percentile([5.0], 0.99) == 5.0
    assert performance_grpc._percentile([10.0, 20.0], 0.5) == 15.0


def test_evaluate_thresholds_covers_rule_shapes_and_skips():
    result = performance_grpc._evaluate_thresholds(
        {"rps": 120.0, "p95_ms": 250.0, "error_rate": None},
        {
            "rps": ">=100",
            "p95_ms": [">=1", "bogus"],
            "error_rate": "<1",
            "missing": "<1",
        },
    )
    assert result == {"rps": {">=100": {"ok": True}}, "p95_ms": {">=1": {"ok": True}}}
    assert performance_grpc._evaluate_thresholds({"rps": 1.0}, {"rps": 123}) == {}
    assert performance_grpc._evaluate_thresholds({"rps": 1.0}, {"rps": ["bogus"]}) == {}
    assert performance_grpc._evaluate_thresholds({"rps": 1.0}, "not-a-mapping") == {}


def test_create_channel_applies_server_name_override(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(performance_grpc, "grpc", _fake_grpc(captured))

    channel = performance_grpc._create_channel(
        {"target": "api.example.test:50051", "use_tls": True, "tls_server_name": "override.example.test"}
    )

    assert channel == "tls-channel"
    assert captured["tls_target"] == "api.example.test:50051"
    assert captured["credentials"] == "fake-credentials"
    assert captured["options"] == [("grpc.ssl_target_name_override", "override.example.test")]


def test_create_channel_rejects_two_certificate_sources(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(performance_grpc, "grpc", _fake_grpc(captured))

    with pytest.raises(GrpcPerformanceOptionsError, match="only one of"):
        performance_grpc._create_channel(
            {
                "target": "api.example.test:50051",
                "use_tls": True,
                "tls_root_certificates": "-----BEGIN CERTIFICATE-----",
                "tls_root_certificates_file": "/etc/ssl/ca.pem",
            }
        )


def test_create_channel_reads_certificate_files(monkeypatch, tmp_path):
    captured: dict = {}
    monkeypatch.setattr(performance_grpc, "grpc", _fake_grpc(captured))

    ca_file = tmp_path / "ca.pem"
    ca_file.write_bytes(b"-----BEGIN CERTIFICATE-----\nCA")
    performance_grpc._create_channel(
        {"target": "api.example.test:50051", "use_tls": True, "tls_root_certificates_file": str(ca_file)}
    )
    assert captured["root_certificates"] == b"-----BEGIN CERTIFICATE-----\nCA"

    with pytest.raises(GrpcPerformanceOptionsError, match="cannot read gRPC root certificate file"):
        performance_grpc._create_channel(
            {
                "target": "api.example.test:50051",
                "use_tls": True,
                "tls_root_certificates_file": str(tmp_path / "missing.pem"),
            }
        )

    junk = tmp_path / "junk.pem"
    junk.write_bytes(b"not-a-pem")
    with pytest.raises(GrpcPerformanceOptionsError, match="must contain a PEM certificate"):
        performance_grpc._create_channel(
            {"target": "api.example.test:50051", "use_tls": True, "tls_root_certificates_file": str(junk)}
        )


def test_run_grpc_script_raises_when_worker_slot_crashes(monkeypatch):
    def crashing_slot(*_args, **_kwargs):
        raise RuntimeError("slot exploded")

    _install_minio(monkeypatch)
    monkeypatch.setattr(performance_grpc, "_run_grpc_slot", crashing_slot)

    with pytest.raises(RuntimeError, match="slot exploded"):
        performance_grpc.run_grpc_script(run_id=11, script_object_name="scripts/echo.proto", options=_valid_options())


def test_run_grpc_script_stops_at_duration_boundary(monkeypatch):
    observed: dict = {}

    def blocking_slot(call, options, request_class, request_bytes, metadata, stats, stop_event):
        observed["duration_seconds"] = options["duration_seconds"]
        stop_event.wait(timeout=5)

    uploads = _install_minio(monkeypatch)
    monkeypatch.setattr(performance_grpc, "_run_grpc_slot", blocking_slot)

    summary, object_name, _duration_ms = performance_grpc.run_grpc_script(
        run_id=11, script_object_name="scripts/echo.proto", options=_valid_options()
    )

    assert observed["duration_seconds"] == pytest.approx(0.001)
    assert summary["iterations"] == 0
    assert summary["exit_code"] == 1
    assert object_name == "performance/runs/11/summary.json"
    assert uploads[0][0] == "performance/runs/11/summary.json"


def test_run_grpc_script_swallows_metric_callback_errors(monkeypatch):
    calls = []

    def blocking_slot(*_args, **_kwargs):
        _args[-1].wait(timeout=5)

    def callback():
        calls.append(1)
        raise RuntimeError("sampler down")

    _install_minio(monkeypatch)
    monkeypatch.setattr(performance_grpc, "_run_grpc_slot", blocking_slot)

    summary, _object_name, _duration = performance_grpc.run_grpc_script(
        run_id=11,
        script_object_name="scripts/echo.proto",
        options=_valid_options(),
        metric_callback=callback,
    )

    assert calls == [1]
    assert summary["iterations"] == 0


def test_run_grpc_script_stops_at_iteration_limit(monkeypatch):
    def recording_slot(call, options, request_class, request_bytes, metadata, stats, stop_event):
        stats.record(1.0, "OK", False, 1)
        stats.record(1.0, "OK", False, 1)
        stop_event.wait(timeout=5)

    _install_minio(monkeypatch)
    monkeypatch.setattr(performance_grpc, "_run_grpc_slot", recording_slot)

    summary, _object_name, _duration = performance_grpc.run_grpc_script(
        run_id=11, script_object_name="scripts/echo.proto", options=_valid_options(iterations=2)
    )

    assert summary["iterations"] == 2
    assert summary["exit_code"] == 0


def test_run_grpc_slot_returns_at_deadline_without_calls():
    stats = performance_grpc._GrpcStats()
    performance_grpc._run_grpc_slot(
        call=lambda *_args, **_kwargs: None,
        options={"duration_seconds": 0.0, "iterations": None, "mode": "unary", "timeout_seconds": 1.0},
        request_class=None,
        request_bytes=[b"x"],
        metadata=[],
        stats=stats,
        stop_event=threading.Event(),
    )
    assert stats.total == 0


def test_run_grpc_slot_counts_non_integer_responses(monkeypatch):
    monkeypatch.setattr(performance_grpc, "_invoke_call", lambda *_args, **_kwargs: None)
    stats = performance_grpc._GrpcStats()
    performance_grpc._run_grpc_slot(
        call=lambda *_args, **_kwargs: None,
        options={"duration_seconds": 30.0, "iterations": 1, "mode": "unary", "timeout_seconds": 1.0},
        request_class=None,
        request_bytes=[b"x"],
        metadata=[],
        stats=stats,
        stop_event=threading.Event(),
    )
    assert stats.total == 1
    assert stats.responses == 1
    assert stats.failures == 0


def test_run_grpc_slot_maps_unexpected_errors_to_internal():
    class _ExplodingRequest:
        @staticmethod
        def FromString(_payload):
            raise ValueError("boom")

    stats = performance_grpc._GrpcStats()
    performance_grpc._run_grpc_slot(
        call=lambda *_args, **_kwargs: None,
        options={"duration_seconds": 30.0, "iterations": 1, "mode": "unary", "timeout_seconds": 1.0},
        request_class=_ExplodingRequest,
        request_bytes=[b"x"],
        metadata=[],
        stats=stats,
        stop_event=threading.Event(),
    )
    assert stats.total == 1
    assert stats.failures == 1
    assert stats.statuses["INTERNAL"] == 1
