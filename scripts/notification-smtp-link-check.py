#!/usr/bin/env python3
"""Verify the email notification path against a real local SMTP session.

This is a LINK-LEVEL self check, not a release acceptance run. It proves that
``send_notification_channel`` builds a valid message, normalises recipients and
completes a real SMTP envelope, using a throwaway sink bound to 127.0.0.1.
It cannot prove provider-side delivery, so the report status is always
``local_link_only`` and the external SMTP/WeCom/DingTalk gate stays open.

Usage::

    backend/.venv/bin/python scripts/notification-smtp-link-check.py \
      --report docs/evidence/notification-smtp-link-check-YYYY-MM-DD.json
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from email import message_from_bytes
import json
from pathlib import Path
import socket
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.models.notification import NotifyChannel  # noqa: E402
from app.services.notifier import send_notification_channel  # noqa: E402


SUMMARY = {
    "title": "ATP 邮件链路自检",
    "status": "failed",
    "total": 1000,
    "passed": 975,
    "failed": 20,
    "error": 5,
    "duration_ms": 120_000,
    "trigger_type": "manual",
    "entity_type": "performance",
    "rps": 128.5,
    "p95_ms": 230,
    "p99_ms": 410,
    "error_rate": 0.025,
    "threshold_status": "failed",
    "performance_event_reasons": ["threshold_failed", "baseline_regression"],
}

# 使用 example.com / example.org（RFC 2606 保留域），确保本检查不会触达真实邮箱。
DISPLAY_NAME_RECIPIENT = "QA Team <ops@example.org>"
RECIPIENTS = ["qa@example.com", "  ", DISPLAY_NAME_RECIPIENT]
EXPECTED_ENVELOPE = ["qa@example.com", "ops@example.org"]

EXPECTED_FIELDS = {
    "rps": ("请求速率", "128.5"),
    "p95_ms": ("P95 延迟", "230ms"),
    "p99_ms": ("P99 延迟", "410ms"),
    "error_rate": ("错误率", "2.50%"),
    "threshold_status": ("阈值", "失败"),
    "performance_event_reasons": ("触发原因", "阈值失败, 基线回归"),
}


class SmtpSink:
    """最小 SMTP 接收端：只实现验收需要的命令，只监听回环地址。"""

    def __init__(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self._server.settimeout(20)
        self.port: int = self._server.getsockname()[1]
        self.mail_from: str | None = None
        self.rcpt_to: list[str] = []
        self.data: bytes = b""
        self.error: str | None = None
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def join(self, timeout: float = 25.0) -> None:
        self._thread.join(timeout)

    def _serve(self) -> None:
        try:
            conn, _ = self._server.accept()
        except Exception as exc:  # pragma: no cover - 本地回环 accept 失败
            self.error = f"accept failed: {type(exc).__name__}"
            self._server.close()
            return
        with conn:
            conn.settimeout(20)
            buffer = b""
            conn.sendall(b"220 127.0.0.1 ATP-SMTP-Sink\r\n")
            reading_data = False
            while True:
                try:
                    chunk = conn.recv(65536)
                except Exception as exc:
                    self.error = f"recv failed: {type(exc).__name__}"
                    break
                if not chunk:
                    break
                buffer += chunk
                if reading_data:
                    if b"\r\n.\r\n" in buffer:
                        body, _, buffer = buffer.partition(b"\r\n.\r\n")
                        self.data = body
                        reading_data = False
                        conn.sendall(b"250 OK queued\r\n")
                    else:
                        continue
                while b"\r\n" in buffer and not reading_data:
                    line, _, buffer = buffer.partition(b"\r\n")
                    text = line.decode("utf-8", "replace")
                    upper = text.upper()
                    if upper.startswith("EHLO") or upper.startswith("HELO"):
                        conn.sendall(b"250-127.0.0.1 greets you\r\n250 8BITMIME\r\n")
                    elif upper.startswith("MAIL FROM:"):
                        self.mail_from = text.split(":", 1)[1].strip()
                        conn.sendall(b"250 OK\r\n")
                    elif upper.startswith("RCPT TO:"):
                        self.rcpt_to.append(text.split(":", 1)[1].strip())
                        conn.sendall(b"250 OK\r\n")
                    elif upper.startswith("DATA"):
                        conn.sendall(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                        reading_data = True
                    elif upper.startswith("QUIT"):
                        conn.sendall(b"221 Bye\r\n")
                        self._server.close()
                        return
                    elif upper.startswith("RSET") or upper.startswith("NOOP"):
                        conn.sendall(b"250 OK\r\n")
                    else:
                        conn.sendall(b"502 Command not implemented\r\n")
        self._server.close()


def _strip_angle_brackets(value: str) -> str:
    return value.strip().lstrip("<").rstrip(">").split(" ", 1)[0]


def _plain_text_part(message) -> str:
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True) or b""
            return payload.decode(part.get_content_charset() or "utf-8", "replace")
    return ""


def _write_report(path: Path, checks: list[dict], *, status: str, port: int) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "scope": "local SMTP link only; does not close the external SMTP/WeCom/DingTalk delivery gate",
        "channel": "smtp-local-sink",
        "environment": {"sink_host": "127.0.0.1", "sink_port": port, "tls": False},
        "checks": checks,
        "credential_values_recorded": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    sink = SmtpSink()
    sink.start()

    settings.SMTP_HOST = "127.0.0.1"
    settings.SMTP_PORT = sink.port
    settings.SMTP_SSL = False
    settings.SMTP_TLS = False
    settings.SMTP_USER = ""
    settings.SMTP_PASSWORD = ""
    settings.SMTP_FROM = "atp-link-check@example.com"

    config = {"recipients": list(RECIPIENTS), "subject_prefix": "[ATP LINK CHECK]"}
    try:
        attempts = asyncio.run(send_notification_channel(NotifyChannel.email, config, SUMMARY))
        record("send_notification_channel completed", True, f"attempts={attempts}")
    except Exception as exc:
        record("send_notification_channel completed", False, f"{type(exc).__name__}: {exc}")
        _write_report(args.report, checks, status="failed", port=sink.port)
        return 1
    finally:
        sink.join()

    if sink.error:
        record("smtp sink session", False, sink.error)
        _write_report(args.report, checks, status="failed", port=sink.port)
        return 1

    record("smtp envelope sender", bool(sink.mail_from), f"MAIL FROM accepted: {bool(sink.mail_from)}")

    envelope = [_strip_angle_brackets(item) for item in sink.rcpt_to]
    record(
        "recipient normalisation in envelope",
        envelope == EXPECTED_ENVELOPE,
        f"RCPT TO={envelope}; blank entry skipped and display name reduced to a bare address",
    )

    message = message_from_bytes(sink.data)
    record("message is MIME multipart", message.is_multipart(), f"content_type={message.get_content_type()}")
    record(
        "display name preserved in To header",
        DISPLAY_NAME_RECIPIENT in str(message.get("To", "")),
        "To header keeps the configured display name",
    )

    text = _plain_text_part(message)
    record("plain text part decoded", bool(text), f"chars={len(text)}")
    for field, (label, value) in EXPECTED_FIELDS.items():
        record(f"body field {field}", f"{label}: {value}" in text, f"expected '{label}: {value}'")

    failed = [item["name"] for item in checks if item["status"] == "FAIL"]
    status = "failed" if failed else "local_link_only"
    _write_report(args.report, checks, status=status, port=sink.port)
    if failed:
        print(f"[FAIL] {len(failed)} check(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("[OK] local SMTP link verified; provider delivery evidence is still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
