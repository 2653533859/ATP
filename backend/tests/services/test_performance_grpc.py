import pytest
import grpc
from concurrent.futures import ThreadPoolExecutor
import json
from google.protobuf import descriptor_pool, message_factory
from unittest.mock import Mock

from app.services import performance_grpc
from app.services.performance_grpc import (
    GrpcPerformanceOptionsError,
    summarize_grpc_samples,
    validate_grpc_options,
)


PROTO = """
syntax = "proto3";
package demo.v1;
message HelloRequest { string name = 1; }
message HelloReply { string text = 1; }
service Greeter {
  rpc Unary(HelloRequest) returns (HelloReply);
  rpc ServerStream(HelloRequest) returns (stream HelloReply);
  rpc ClientStream(stream HelloRequest) returns (HelloReply);
  rpc Bidi(stream HelloRequest) returns (stream HelloReply);
}
"""


def _start_grpc_server():
    descriptor_set = performance_grpc.compile_grpc_proto(PROTO)
    pool = descriptor_pool.DescriptorPool()
    for file_proto in descriptor_set.file:
        pool.Add(file_proto)
    request_class = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.v1.HelloRequest"))
    response_class = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.v1.HelloReply"))

    def unary(request, _context):
        return response_class(text=f"hello {request.name}")

    def server_stream(request, _context):
        for index in range(2):
            yield response_class(text=f"hello {request.name} {index}")

    def client_stream(requests, _context):
        return response_class(text=",".join(request.name for request in requests))

    def bidi(requests, _context):
        for request in requests:
            yield response_class(text=f"hello {request.name}")

    handlers = {
        "Unary": grpc.unary_unary_rpc_method_handler(
            unary,
            request_deserializer=request_class.FromString,
            response_serializer=response_class.SerializeToString,
        ),
        "ServerStream": grpc.unary_stream_rpc_method_handler(
            server_stream,
            request_deserializer=request_class.FromString,
            response_serializer=response_class.SerializeToString,
        ),
        "ClientStream": grpc.stream_unary_rpc_method_handler(
            client_stream,
            request_deserializer=request_class.FromString,
            response_serializer=response_class.SerializeToString,
        ),
        "Bidi": grpc.stream_stream_rpc_method_handler(
            bidi,
            request_deserializer=request_class.FromString,
            response_serializer=response_class.SerializeToString,
        ),
    }
    server = grpc.server(ThreadPoolExecutor(max_workers=8))
    server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler("demo.v1.Greeter", handlers),))
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    return server, port


def _stub_minio(monkeypatch, proto=PROTO):
    uploaded = []

    def download(_object_name, path):
        path.write_text(proto, encoding="utf-8")

    def upload(object_name, path, *, content_type):
        uploaded.append((object_name, path.read_text(encoding="utf-8"), content_type))

    monkeypatch.setattr(performance_grpc.minio_client, "download_file", download, raising=False)
    monkeypatch.setattr(performance_grpc.minio_client, "upload_file", upload, raising=False)
    return uploaded


def test_validate_grpc_options_normalizes_unary_tls_and_metadata():
    result = validate_grpc_options(
        {
            "target": "grpcs://api.example.test:50051",
            "service": "demo.v1.Greeter",
            "method": "SayHello",
            "request": {"name": "ATP"},
            "metadata": {"authorization": "{{API_TOKEN}}", "x-tenant": "demo"},
            "use_tls": True,
            "timeout_seconds": 12,
        }
    )

    assert result["target"] == "api.example.test:50051"
    assert result["mode"] == "unary"
    assert result["metadata"]["authorization"] == "{{API_TOKEN}}"
    assert result["use_tls"] is True


def test_validate_grpc_options_accepts_public_custom_root_certificate():
    result = validate_grpc_options(
        {
            "target": "grpcs://grpc-target:50051",
            "service": "demo.v1.Greeter",
            "method": "Unary",
            "tls_root_certificates": "-----BEGIN CERTIFICATE-----\\npublic-ca\\n-----END CERTIFICATE-----",
        }
    )

    assert "BEGIN CERTIFICATE" in result["tls_root_certificates"]


def test_create_channel_passes_custom_root_certificate_to_grpc(monkeypatch):
    channel = Mock()
    captured = {}

    def secure_channel(target, credentials, *, options):
        captured.update(target=target, credentials=credentials, options=options)
        return channel

    monkeypatch.setattr(performance_grpc.grpc, "secure_channel", secure_channel)
    result = performance_grpc._create_channel(
        {
            "target": "grpc-target:50051",
            "use_tls": True,
            "tls_root_certificates": "-----BEGIN CERTIFICATE-----\\npublic-ca\\n-----END CERTIFICATE-----",
        }
    )

    assert result is channel
    assert captured["target"] == "grpc-target:50051"
    assert captured["credentials"] is not None


def test_validate_grpc_options_accepts_worker_mounted_root_certificate_file():
    result = validate_grpc_options(
        {
            "target": "grpcs://grpc-target:50051",
            "service": "demo.v1.Greeter",
            "method": "Unary",
            "tls_root_certificates_file": "/etc/atp/tls/server.crt",
        }
    )

    assert result["tls_root_certificates_file"] == "/etc/atp/tls/server.crt"


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"service": "demo.Greeter", "method": "SayHello"}, "target"),
        ({"target": "api.example.test", "service": "demo.Greeter", "method": "SayHello"}, "host:port"),
        (
            {
                "target": "api.example.test:50051",
                "service": "demo.Greeter",
                "method": "SayHello",
                "metadata": {"authorization": "Bearer secret"},
            },
            "敏感 metadata",
        ),
    ],
)
def test_validate_grpc_options_rejects_incomplete_or_secret_inline_values(options, message):
    with pytest.raises(GrpcPerformanceOptionsError, match=message):
        validate_grpc_options(options)


def test_summarize_grpc_samples_returns_common_metrics_and_statuses():
    result = summarize_grpc_samples(
        [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        failures=2,
        duration_ms=1000,
        total_requests=10,
        statuses={"OK": 8, "UNAVAILABLE": 2},
    )

    assert result["executor"] == "grpc"
    assert result["rps"] == 10
    assert result["p95_ms"] == pytest.approx(95.5)
    assert result["p99_ms"] == pytest.approx(99.1)
    assert result["error_rate"] == 0.2
    assert result["grpc_statuses"] == {"OK": 8, "UNAVAILABLE": 2}


@pytest.mark.parametrize("mode", ["unary", "server_stream", "client_stream", "bidi_stream"])
def test_run_grpc_script_exercises_real_unary_and_streaming_service(monkeypatch, mode):
    uploaded = _stub_minio(monkeypatch)
    server, port = _start_grpc_server()
    try:
        summary, object_name, duration_ms = performance_grpc.run_grpc_script(
            run_id=901,
            script_object_name="performance/scripts/greeter.proto",
            options={
                "target": f"127.0.0.1:{port}",
                "service": "demo.v1.Greeter",
                "method": {
                    "unary": "Unary",
                    "server_stream": "ServerStream",
                    "client_stream": "ClientStream",
                    "bidi_stream": "Bidi",
                }[mode],
                "mode": mode,
                "request": {"name": "ATP"},
                "requests": [{"name": "ATP"}, {"name": "load"}],
                "concurrency": 2,
                "iterations": 6,
                "timeout_seconds": 2,
            },
        )
    finally:
        server.stop(0)

    assert summary["exit_code"] == 0
    assert summary["iterations"] == 6
    assert summary["grpc_statuses"] == {"OK": 6}
    assert summary["grpc_responses"] >= 6
    assert duration_ms >= 0
    assert object_name == "performance/runs/901/summary.json"
    assert uploaded and uploaded[0][2] == "application/json"


def test_run_grpc_script_reports_rpc_failures_without_leaking_request_data(monkeypatch):
    _stub_minio(monkeypatch)
    summary, _object_name, _duration_ms = performance_grpc.run_grpc_script(
        run_id=902,
        script_object_name="performance/scripts/greeter.proto",
        options={
            "target": "127.0.0.1:1",
            "service": "demo.v1.Greeter",
            "method": "Unary",
            "request": {"name": "secret-placeholder"},
            "iterations": 2,
            "timeout_seconds": 0.2,
        },
    )

    assert summary["exit_code"] == 1
    assert summary["iterations"] == 2
    assert summary["error_rate"] == 1
    assert "secret-placeholder" not in json.dumps(summary)


def test_run_grpc_script_honors_cancellation(monkeypatch):
    _stub_minio(monkeypatch)
    with pytest.raises(performance_grpc.PerformanceRunCancelled):
        performance_grpc.run_grpc_script(
            run_id=903,
            script_object_name="performance/scripts/greeter.proto",
            options={
                "target": "127.0.0.1:1",
                "service": "demo.v1.Greeter",
                "method": "Unary",
                "request": {},
                "duration_seconds": 60,
                "timeout_seconds": 30,
            },
            cancel_check=lambda: True,
        )
