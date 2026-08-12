"""Black-box tests for the standalone performance acceptance target."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import threading
from urllib.request import urlopen

import grpc


ROOT = Path(__file__).resolve().parents[3]


def _load_target():
    path = ROOT / "scripts" / "performance_acceptance_target.py"
    spec = importlib.util.spec_from_file_location("performance_acceptance_target", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_target_serves_real_unary_grpc_and_http_health():
    target = _load_target()
    grpc_server, grpc_port = target.build_grpc_server("127.0.0.1", 0)
    http_server = target.build_http_server("127.0.0.1", 0)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    grpc_server.start()
    http_thread.start()
    request_class, response_class = target._message_classes()
    try:
        channel = grpc.insecure_channel(f"127.0.0.1:{grpc_port}")
        call = channel.unary_unary(
            "/demo.v1.Greeter/Unary",
            request_serializer=request_class.SerializeToString,
            response_deserializer=response_class.FromString,
        )
        # gRPC server.start() returns before the listening socket is guaranteed
        # to accept connections on slower Windows CI hosts.  Wait for readiness
        # so this test validates the handler rather than a startup race.
        response = call(request_class(name="ATP"), timeout=5, wait_for_ready=True)
        assert response.text == "hello ATP"
        with urlopen(f"http://127.0.0.1:{http_server.server_port}/healthz", timeout=2) as result:
            assert result.status == 200
        channel.close()
    finally:
        http_server.shutdown()
        http_server.server_close()
        grpc_server.stop(0).wait()
        http_thread.join(timeout=2)
