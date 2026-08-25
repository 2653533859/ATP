"""Standalone gRPC and HTTP targets for ATP performance acceptance.

This process is deliberately independent from the ATP database, Redis, and
MinIO services.  It provides deterministic unary/streaming gRPC methods and a
small HTTP endpoint so a dedicated performance worker can be validated over a
real container network.  TLS certificates are supplied by the deployment
environment; the script never generates or logs private keys.
"""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import struct
import threading
from typing import Any
from urllib.parse import urlsplit

import grpc
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from grpc_tools import protoc


PROTO = """
syntax = "proto3";
package demo.v1;

message HelloRequest { string name = 1; }
message HelloReply { string text = 1; int32 sequence = 2; }

service Greeter {
  rpc Unary(HelloRequest) returns (HelloReply);
  rpc ServerStream(HelloRequest) returns (stream HelloReply);
  rpc ClientStream(stream HelloRequest) returns (HelloReply);
  rpc Bidi(stream HelloRequest) returns (stream HelloReply);
}
"""


def _message_classes() -> tuple[Any, Any]:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory(prefix="atp-acceptance-proto-") as tmpdir:
        proto_path = Path(tmpdir) / "acceptance.proto"
        descriptor_path = Path(tmpdir) / "acceptance.bin"
        proto_path.write_text(PROTO, encoding="utf-8")
        result = protoc.main(
            [
                "protoc",
                f"--proto_path={tmpdir}",
                f"--descriptor_set_out={descriptor_path}",
                "--include_imports",
                str(proto_path),
            ]
        )
        if result != 0:
            raise RuntimeError("failed to compile acceptance proto")

        pool = descriptor_pool.DescriptorPool()
        files = descriptor_pb2.FileDescriptorSet.FromString(descriptor_path.read_bytes())
        for file_proto in files.file:
            pool.Add(file_proto)
        request = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.v1.HelloRequest"))
        response = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.v1.HelloReply"))
        return request, response


def build_grpc_server(bind: str, port: int, *, certificate: Path | None = None, private_key: Path | None = None):
    """Build and bind the deterministic generic gRPC server."""
    if (certificate is None) != (private_key is None):
        raise ValueError("certificate and private_key must be supplied together")

    request_class, response_class = _message_classes()

    def unary(request, _context):
        return response_class(text=f"hello {request.name}", sequence=0)

    def server_stream(request, _context):
        for sequence in range(2):
            yield response_class(text=f"hello {request.name} {sequence}", sequence=sequence)

    def client_stream(requests, _context):
        names = [request.name for request in requests]
        return response_class(text=",".join(names), sequence=len(names))

    def bidi(requests, _context):
        for sequence, request in enumerate(requests):
            yield response_class(text=f"hello {request.name}", sequence=sequence)

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
    server = grpc.server(ThreadPoolExecutor(max_workers=16))
    server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler("demo.v1.Greeter", handlers),))

    if certificate is None:
        bound_port = server.add_insecure_port(f"{bind}:{port}")
    else:
        cert_bytes = certificate.read_bytes()
        key_bytes = private_key.read_bytes() if private_key else b""
        credentials = grpc.ssl_server_credentials(((key_bytes, cert_bytes),))
        bound_port = server.add_secure_port(f"{bind}:{port}", credentials)
    if not bound_port:
        raise OSError(f"could not bind gRPC target on {bind}:{port}")
    return server, bound_port


class _HttpHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ATP-Performance-Target/1.1"
    _MAX_HTTP_BODY_BYTES = 1024 * 1024
    _WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            self._serve_websocket()
            return
        if path not in {"/", "/healthz", "/api/hello"}:
            self.send_error(404)
            return
        self._send_json(200, {"status": "ok", "service": "atp-performance-target"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if urlsplit(self.path).path != "/graphql":
            self.send_error(404)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"errors": [{"message": "invalid content length"}]})
            return
        if content_length < 0 or content_length > self._MAX_HTTP_BODY_BYTES:
            self._send_json(413, {"errors": [{"message": "request body too large"}]})
            return
        try:
            raw_body = self.rfile.read(content_length)
            request = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"errors": [{"message": "request body must be JSON"}]})
            return
        if not isinstance(request, dict) or not isinstance(request.get("query"), str) or not request["query"].strip():
            self._send_json(400, {"errors": [{"message": "query is required"}]})
            return

        variables = request.get("variables")
        if not isinstance(variables, dict):
            variables = {}
        name = str(variables.get("name") or "ATP")
        data: dict[str, Any] = {
            "hello": f"hello {name}",
            "service": "atp-graphql-target",
            "echo": variables,
        }
        if "viewer" in request["query"]:
            data["viewer"] = {"name": "ATP", "role": "acceptance"}
        self._send_json(200, {"data": data})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_websocket(self) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400, "missing websocket key")
            return
        accept = base64.b64encode(hashlib.sha1((key + self._WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")
        self.send_response_only(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.connection.settimeout(30)
        try:
            while True:
                frame = self._read_websocket_frame()
                if frame is None:
                    return
                opcode, payload = frame
                if opcode == 0x8:  # close
                    self._write_websocket_frame(0x8, payload[:125])
                    return
                if opcode == 0x9:  # ping
                    self._write_websocket_frame(0xA, payload)
                    continue
                if opcode != 0x1:  # only text frames are needed by the acceptance executor
                    self._write_websocket_frame(0x8, b"\x03\xeaunsupported frame")
                    return
                try:
                    decoded: Any = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    decoded = payload.decode("utf-8", errors="replace")
                response = {
                    "ok": True,
                    "service": "atp-websocket-target",
                    "echo": decoded,
                }
                self._write_websocket_frame(0x1, json.dumps(response, ensure_ascii=False).encode("utf-8"))
        except (ConnectionError, OSError, TimeoutError):
            return
        finally:
            self.close_connection = True

    def _read_websocket_frame(self) -> tuple[int, bytes] | None:
        header = self._read_exact(2)
        if not header:
            return None
        first, second = header
        if not first & 0x80:
            self._write_websocket_frame(0x8, b"\x03\xeafragmentation unsupported")
            return None
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        if length > self._MAX_HTTP_BODY_BYTES or not masked:
            self._write_websocket_frame(0x8, b"\x03\xeainvalid frame")
            return None
        mask = self._read_exact(4)
        payload = self._read_exact(length)
        return opcode, bytes(value ^ mask[index % 4] for index, value in enumerate(payload))

    def _read_exact(self, length: int) -> bytes:
        data = self.rfile.read(length)
        if len(data) != length:
            raise ConnectionError("incomplete websocket frame")
        return data

    def _write_websocket_frame(self, opcode: int, payload: bytes) -> None:
        length = len(payload)
        if length < 126:
            header = bytes([0x80 | opcode, length])
        elif length <= 0xFFFF:
            header = bytes([0x80 | opcode, 126]) + struct.pack("!H", length)
        else:
            header = bytes([0x80 | opcode, 127]) + struct.pack("!Q", length)
        self.wfile.write(header + payload)
        self.wfile.flush()

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def build_http_server(bind: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((bind, port), _HttpHandler)
    server.daemon_threads = True
    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grpc-bind", default="0.0.0.0")
    parser.add_argument("--grpc-port", type=int, default=50051)
    parser.add_argument("--grpc-certificate", type=Path)
    parser.add_argument("--grpc-private-key", type=Path)
    parser.add_argument("--http-bind", default="0.0.0.0")
    parser.add_argument("--http-port", type=int, default=8080)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    grpc_server, grpc_port = build_grpc_server(
        args.grpc_bind,
        args.grpc_port,
        certificate=args.grpc_certificate,
        private_key=args.grpc_private_key,
    )
    http_server = build_http_server(args.http_bind, args.http_port)
    stop = threading.Event()

    def request_stop(_signal: int, _frame: Any) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    grpc_server.start()
    http_thread = threading.Thread(target=http_server.serve_forever, name="http-target", daemon=True)
    http_thread.start()
    print(f"performance target ready grpc={grpc_port} http={args.http_port}", flush=True)
    try:
        while not stop.wait(1):
            pass
    finally:
        http_server.shutdown()
        http_server.server_close()
        grpc_server.stop(5).wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
