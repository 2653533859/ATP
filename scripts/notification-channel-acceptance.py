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
from app.models.notification import NotifyChannel  # noqa: E402
from app.services.notifier import (  # noqa: E402
    _build_markdown,
    _build_text,
    _safe_exception_message,
    send_notification_channel,
)


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


def _content_checks() -> dict[str, bool]:
    """按渠道正文实际内容逐字段核对，不允许把未验证的字段记成通过。

    逐项匹配“标签 + 取值”，避免某个字段的取值恰好包含另一个字段的标签而误判通过。
    """

    text = _build_text(SUMMARY)
    markdown = _build_markdown(SUMMARY)
    expected = {
        "rps": ("请求速率", "128.5"),
        "p95_ms": ("P95 延迟", "230ms"),
        "p99_ms": ("P99 延迟", "410ms"),
        "error_rate": ("错误率", "2.50%"),
        "threshold_status": ("阈值", "失败"),
        "performance_event_reasons": ("触发原因", "阈值失败, 基线回归"),
    }
    return {
        field: f"{label}: {value}" in text and f"**{label}**: {value}" in markdown
        for field, (label, value) in expected.items()
    }


def _report(path: Path, channel: str, status: str, detail: str, content_checks: dict[str, bool]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "channel": channel,
        "delivery": detail,
        "content_checks": content_checks,
        "credential_values_recorded": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def _send(channel: str) -> str:
    """走生产投递入口 send_notification_channel，确保验收覆盖真实校验与重试策略。"""

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
        config = {"recipients": recipients, "subject_prefix": "[ATP ACCEPTANCE]"}
        attempts = await send_notification_channel(NotifyChannel.email, config, SUMMARY)
        return f"SMTP server accepted the message after {attempts} attempt(s); retain recipient-side receipt evidence"

    env_name = "ATP_ACCEPTANCE_WECOM_WEBHOOK_URL" if channel == "wecom" else "ATP_ACCEPTANCE_DINGTALK_WEBHOOK_URL"
    webhook_url = os.getenv(env_name, "").strip()
    if not webhook_url:
        raise ValueError(f"缺少配置: {env_name}")
    validate_public_http_url(webhook_url)
    if channel == "wecom":
        attempts = await send_notification_channel(NotifyChannel.wechat, {"webhook_url": webhook_url}, SUMMARY)
        return f"WeCom returned errcode=0 after {attempts} attempt(s)"
    attempts = await send_notification_channel(
        NotifyChannel.dingtalk,
        {"webhook_url": webhook_url, "secret": os.getenv("ATP_ACCEPTANCE_DINGTALK_SECRET", "")},
        SUMMARY,
    )
    return f"DingTalk returned errcode=0 after {attempts} attempt(s)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", choices=("smtp", "wecom", "dingtalk"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    content_checks = _content_checks()
    missing_fields = sorted(field for field, ok in content_checks.items() if not ok)
    if missing_fields:
        detail = f"notification content is incomplete: {', '.join(missing_fields)}"
        _report(args.report, args.channel, "failed", detail, content_checks)
        print(f"[FAIL] {detail}", file=sys.stderr)
        return 1

    try:
        detail = asyncio.run(_send(args.channel))
    except Exception as exc:
        safe_detail = _safe_exception_message(exc)
        _report(args.report, args.channel, "failed", safe_detail, content_checks)
        print(f"[FAIL] {args.channel}: {safe_detail}", file=sys.stderr)
        return 1

    _report(args.report, args.channel, "passed", detail, content_checks)
    print(f"[PASS] {args.channel}: {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
