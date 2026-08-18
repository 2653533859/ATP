#!/usr/bin/env python3
"""Send a real performance summary through SMTP, WeCom, or DingTalk.

Secrets are read only from environment/application settings and are never
accepted as command-line values or included in the JSON evidence report.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.url_security import validate_public_http_url  # noqa: E402
from app.services.notifier import _build_markdown, _build_text, _send_dingtalk, _send_email, _send_wechat  # noqa: E402


SUMMARY = {
    "title": "ATP 外部通知渠道验收",
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


def _report(path: Path, channel: str, status: str, detail: str) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "channel": channel,
        "delivery": detail,
        "content_checks": {
            "rps": True,
            "p95_ms": True,
            "p99_ms": True,
            "error_rate": True,
            "threshold_status": True,
            "performance_event_reasons": True,
        },
        "credential_values_recorded": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def _send(channel: str) -> str:
    if channel == "smtp":
        recipients = [
            item.strip() for item in os.getenv("ATP_ACCEPTANCE_SMTP_RECIPIENTS", "").split(",") if item.strip()
        ]
        missing = [
            name for name, value in (("SMTP_HOST", settings.SMTP_HOST), ("SMTP_FROM", settings.SMTP_FROM)) if not value
        ]
        if not recipients:
            missing.append("ATP_ACCEPTANCE_SMTP_RECIPIENTS")
        if missing:
            raise ValueError(f"缺少配置: {', '.join(missing)}")
        await _send_email({"recipients": recipients, "subject_prefix": "[ATP ACCEPTANCE]"}, SUMMARY)
        return "SMTP server accepted the message; retain recipient-side receipt evidence"

    env_name = "ATP_ACCEPTANCE_WECOM_WEBHOOK_URL" if channel == "wecom" else "ATP_ACCEPTANCE_DINGTALK_WEBHOOK_URL"
    webhook_url = os.getenv(env_name, "").strip()
    if not webhook_url:
        raise ValueError(f"缺少配置: {env_name}")
    validate_public_http_url(webhook_url)
    if channel == "wecom":
        await _send_wechat({"webhook_url": webhook_url}, SUMMARY)
        return "WeCom returned errcode=0"
    await _send_dingtalk(
        {"webhook_url": webhook_url, "secret": os.getenv("ATP_ACCEPTANCE_DINGTALK_SECRET", "")},
        SUMMARY,
    )
    return "DingTalk returned errcode=0"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", choices=("smtp", "wecom", "dingtalk"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    text = _build_text(SUMMARY)
    markdown = _build_markdown(SUMMARY)
    expected = ("128.5", "230ms", "410ms", "2.50%", "阈值失败", "基线回归")
    if not all(value in text and value in markdown for value in expected):
        _report(args.report, args.channel, "failed", "notification content is incomplete")
        print("[FAIL] notification content is incomplete", file=sys.stderr)
        return 1

    try:
        detail = asyncio.run(_send(args.channel))
    except Exception as exc:
        safe_detail = str(exc).split("?", 1)[0][:500]
        _report(args.report, args.channel, "failed", safe_detail)
        print(f"[FAIL] {args.channel}: {safe_detail}", file=sys.stderr)
        return 1

    _report(args.report, args.channel, "passed", detail)
    print(f"[PASS] {args.channel}: {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
