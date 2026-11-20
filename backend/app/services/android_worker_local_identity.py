"""Loopback-only read-only identity HTTP server for local Android Workers.

Browsers cannot invoke local ``adb.exe`` directly when viewing a remote ATP UI.
Running a tiny read-only server bound strictly to ``127.0.0.1`` lets the browser
on the same machine discover which ``worker_id`` owns the local ADB server and
automatically select that node in the UI.  All actual device commands still flow
through the authenticated ATP API and the worker's dedicated Celery queues.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

logger = logging.getLogger(__name__)


class _QuietThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows SO_REUSEADDR allows two live listeners on the same loopback port;
    # keep reuse enabled only on POSIX for quick TIME_WAIT rebinding.
    allow_reuse_address = os.name != "nt"


class AndroidWorkerLocalIdentityServer:
    """Serve ``GET /identity`` on ``127.0.0.1`` with CORS + Private Network Access headers."""

    def __init__(
        self,
        *,
        worker_id: str,
        queues: list[str],
        port: int = 17321,
        hostname: str | None = None,
        generation_fn: Callable[[], int | None] | None = None,
        adb_ok_fn: Callable[[], bool] | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.queues = list(queues)
        self.port = int(port)
        self.hostname = hostname or socket.gethostname()
        self._generation_fn = generation_fn or (lambda: None)
        self._adb_ok_fn = adb_ok_fn or (lambda: shutil.which("adb") is not None)
        self._server: _QuietThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def bound_port(self) -> int | None:
        if self._server is None:
            return None
        return int(self._server.server_address[1])

    def build_payload(self) -> dict[str, Any]:
        try:
            adb_ok = bool(self._adb_ok_fn())
        except Exception:
            adb_ok = False
        try:
            generation = self._generation_fn()
        except Exception:
            generation = None
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "adb_ok": adb_ok,
            "instance_generation": generation,
            "queues": list(self.queues),
        }

    def start(self) -> bool:
        if self._server is not None:
            return True
        if self.port < 0:
            return False

        parent = self

        class _IdentityHandler(BaseHTTPRequestHandler):
            def _write_cors_headers(self) -> None:
                origin = (self.headers.get("Origin") or "").strip()
                self.send_header("Access-Control-Allow-Origin", origin or "*")
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.send_header("Cache-Control", "no-store")

            def do_OPTIONS(self) -> None:  # noqa: N802
                if self.path.split("?", 1)[0] != "/identity":
                    self.send_response(404)
                    self._write_cors_headers()
                    self.end_headers()
                    return
                self.send_response(204)
                self._write_cors_headers()
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                if self.path.split("?", 1)[0] != "/identity":
                    body = b'{"detail":"not_found"}'
                    self.send_response(404)
                    self._write_cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                body = json.dumps(parent.build_payload(), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._write_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

        try:
            server = _QuietThreadingHTTPServer(("127.0.0.1", self.port), _IdentityHandler)
        except OSError as exc:
            logger.warning(
                "Android Worker '%s' skipped local identity server on 127.0.0.1:%s: %s",
                self.worker_id,
                self.port,
                exc,
            )
            return False

        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.2},
            name=f"android-worker-identity-{self.worker_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Android Worker '%s' local identity server listening on http://127.0.0.1:%s/identity",
            self.worker_id,
            self.bound_port,
        )
        return True

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
