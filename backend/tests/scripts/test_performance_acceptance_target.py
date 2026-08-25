"""Black-box tests for the standalone performance acceptance target."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import threading
from urllib.request import Request, urlopen

import grpc
import websockets


ROOT = Path(__file__).resolve().parents[3]


def _load_target():
    path = ROOT / "scripts" / "performance_acceptance_target.py"
    spec = importlib.util.spec_from_file_location("performance_acceptance_target", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_target_serves_real_grpc_modes_and_http_health():
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
        stream_call = channel.unary_stream(
            "/demo.v1.Greeter/ServerStream",
            request_serializer=request_class.SerializeToString,
            response_deserializer=response_class.FromString,
        )
        assert [item.sequence for item in stream_call(request_class(name="ATP"), timeout=5)] == [0, 1]
        client_stream_call = channel.stream_unary(
            "/demo.v1.Greeter/ClientStream",
            request_serializer=request_class.SerializeToString,
            response_deserializer=response_class.FromString,
        )
        client_stream_response = client_stream_call(iter([request_class(name="A"), request_class(name="B")]), timeout=5)
        assert client_stream_response.text == "A,B"
        bidi_call = channel.stream_stream(
            "/demo.v1.Greeter/Bidi",
            request_serializer=request_class.SerializeToString,
            response_deserializer=response_class.FromString,
        )
        bidi_response = bidi_call(iter([request_class(name="A"), request_class(name="B")]), timeout=5)
        assert [item.text for item in bidi_response] == ["hello A", "hello B"]
        with urlopen(f"http://127.0.0.1:{http_server.server_port}/healthz", timeout=2) as result:
            assert result.status == 200
        channel.close()
    finally:
        http_server.shutdown()
        http_server.server_close()
        grpc_server.stop(0).wait()
        http_thread.join(timeout=2)


def test_target_serves_graphql_and_websocket():
    target = _load_target()
    http_server = target.build_http_server("127.0.0.1", 0)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{http_server.server_port}/graphql",
            data=json.dumps(
                {
                    "query": "query Demo($name: String) { hello service viewer }",
                    "variables": {"name": "GraphQL"},
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as result:
            payload = json.loads(result.read().decode("utf-8"))
        assert payload["data"]["hello"] == "hello GraphQL"
        assert payload["data"]["service"] == "atp-graphql-target"
        assert payload["data"]["viewer"]["role"] == "acceptance"

        async def websocket_round_trip() -> dict:
            async with websockets.connect(f"ws://127.0.0.1:{http_server.server_port}/ws") as websocket:
                await websocket.send(json.dumps({"message": "hello"}))
                return json.loads(await websocket.recv())

        response = asyncio.run(websocket_round_trip())
        assert response == {
            "ok": True,
            "service": "atp-websocket-target",
            "echo": {"message": "hello"},
        }
    finally:
        http_server.shutdown()
        http_server.server_close()
        http_thread.join(timeout=2)
