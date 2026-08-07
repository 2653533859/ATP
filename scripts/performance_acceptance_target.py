"""Standalone gRPC and HTTP targets for ATP performance acceptance.

This process is deliberately independent from the ATP database, Redis, and
MinIO services.  It provides deterministic unary/streaming gRPC methods and a
small HTTP endpoint so a dedicated performance worker can be validated over a
real container network.  TLS certificates are supplied by the deployment
environment; the script never generates or logs private keys.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import threading
from typing import Any

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
    server_version = "ATP-Performance-Target/1.0"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path not in {"/", "/healthz", "/api/hello"}:
            self.send_error(404)
            return
        body = json.dumps({"status": "ok", "service": "atp-performance-target"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def build_http_server(bind: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((bind, port), _HttpHandler)


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
