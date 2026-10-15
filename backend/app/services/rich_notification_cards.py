"""Rich notification card payload builders for Enterprise WeChat, DingTalk, and Feishu (P4.1).

Builds:
1. Enterprise WeChat (wechat): template_card and colored Markdown
2. DingTalk (dingtalk): actionCard with singleURL/buttons and colored Markdown
3. Feishu / Lark (feishu): interactive card with template color headers and action buttons
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

# Color maps for different channels
STATUS_COLORS = {
    "passed": {
        "wechat_color": "info",  # Green in WeChat Work
        "wechat_hex": "#07C160",
        "dingtalk_color": "#07C160",
        "feishu_template": "green",
        "badge": "✅",
        "label": "通过",
    },
    "failed": {
        "wechat_color": "warning",  # Red / highlight in WeChat Work
        "wechat_hex": "#FA5151",
        "dingtalk_color": "#FA5151",
        "feishu_template": "red",
        "badge": "❌",
        "label": "失败",
    },
    "error": {
        "wechat_color": "comment",  # Grey / Orange
        "wechat_hex": "#FF9F00",
        "dingtalk_color": "#FF9F00",
        "feishu_template": "orange",
        "badge": "⚠️",
        "label": "异常",
    },
}

DEFAULT_STATUS_COLOR = {
    "wechat_color": "comment",
    "wechat_hex": "#888888",
    "dingtalk_color": "#888888",
    "feishu_template": "blue",
    "badge": "ℹ️",
    "label": "未完成",
}


def get_status_meta(status: str | None) -> dict[str, str]:
    return STATUS_COLORS.get(str(status).lower(), DEFAULT_STATUS_COLOR)


def format_duration(duration_ms: object) -> str:
    if isinstance(duration_ms, (int, float)) and duration_ms > 0:
        return f"{duration_ms / 1000:.1f}s"
    return "-"


def compute_pass_rate(passed: int, total: int) -> str:
    if total > 0:
        return f"{passed / total * 100:.1f}%"
    return "100%" if passed == 0 and total == 0 else "0%"


def build_wechat_template_card(summary: dict[str, Any], report_url: str | None = None) -> dict[str, Any]:
    """Build Enterprise WeChat template_card payload."""
    status = str(summary.get("status", "unknown"))
    meta = get_status_meta(status)
    title = str(summary.get("title") or "ATP 测试执行完成")
    passed = int(summary.get("passed", 0))
    total = int(summary.get("total", 0))
    failed = int(summary.get("failed", 0))
    error = int(summary.get("error", 0))
    duration_str = format_duration(summary.get("duration_ms"))
    pass_rate = compute_pass_rate(passed, total)
    url = report_url or summary.get("report_url") or "https://atp.local"

    horizontal_list: list[dict[str, str]] = [
        {"keyname": "执行状态", "value": f"{meta['badge']} {meta['label']}"},
        {"keyname": "用例总数", "value": f"{total} (通过: {passed})"},
        {"keyname": "失败 / 错误", "value": f"{failed} / {error}"},
        {"keyname": "执行耗时", "value": duration_str},
    ]

    if summary.get("rps") is not None:
        horizontal_list.append({"keyname": "TPS / RPS", "value": str(summary.get("rps"))})
    if summary.get("p95_ms") is not None:
        horizontal_list.append({"keyname": "P95 响应耗时", "value": f"{summary.get('p95_ms')}ms"})

    card: dict[str, Any] = {
        "card_type": "text_notice",
        "source": {
            "icon_url": "https://img.icons8.com/color/48/speed.png",
            "desc": "ATP 自动化测试平台",
            "desc_color": 0,
        },
        "main_title": {
            "title": title,
            "desc": f"状态: {meta['label']} · 耗时 {duration_str}",
        },
        "emphasis_content": {
            "title": pass_rate,
            "desc": "通过率",
        },
        "horizontal_content_list": horizontal_list,
        "jump_list": [
            {
                "type": 1,
                "url": url,
                "title": "查看在线测试报告",
            }
        ],
        "card_action": {
            "type": 1,
            "url": url,
        },
    }

    return {
        "msgtype": "template_card",
        "template_card": card,
    }


def build_dingtalk_action_card(summary: dict[str, Any], report_url: str | None = None) -> dict[str, Any]:
    """Build DingTalk actionCard payload with colored markdown and action button."""
    status = str(summary.get("status", "unknown"))
    meta = get_status_meta(status)
    title = str(summary.get("title") or "ATP 测试执行完成")
    passed = int(summary.get("passed", 0))
    total = int(summary.get("total", 0))
    failed = int(summary.get("failed", 0))
    error = int(summary.get("error", 0))
    duration_str = format_duration(summary.get("duration_ms"))
    pass_rate = compute_pass_rate(passed, total)
    url = report_url or summary.get("report_url") or "https://atp.local"

    lines = [
        f"### {meta['badge']} {title}",
        f"> **状态**: <font color=\"{meta['dingtalk_color']}\">{meta['label']}</font>",
        f"> **通过率**: **{pass_rate}** ({passed}/{total})",
        f'> **失败/错误**: <font color="#FA5151">{failed}</font> / {error}',
        f"> **执行耗时**: {duration_str}",
    ]

    if summary.get("rps") is not None:
        lines.append(f"> **RPS / TPS**: {summary.get('rps')}")
    if summary.get("p95_ms") is not None:
        lines.append(f"> **P95 延迟**: {summary.get('p95_ms')}ms")

    text = "\n\n".join(lines)

    return {
        "msgtype": "actionCard",
        "actionCard": {
            "title": title,
            "text": text,
            "singleTitle": "查看测试报告",
            "singleURL": url,
        },
    }


def build_feishu_interactive_card(summary: dict[str, Any], report_url: str | None = None) -> dict[str, Any]:
    """Build Feishu / Lark interactive message card with color header and action button."""
    status = str(summary.get("status", "unknown"))
    meta = get_status_meta(status)
    title = str(summary.get("title") or "ATP 测试执行完成")
    passed = int(summary.get("passed", 0))
    total = int(summary.get("total", 0))
    failed = int(summary.get("failed", 0))
    error = int(summary.get("error", 0))
    duration_str = format_duration(summary.get("duration_ms"))
    pass_rate = compute_pass_rate(passed, total)
    url = report_url or summary.get("report_url") or "https://atp.local"

    fields: list[dict[str, Any]] = [
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**执行状态**\n{meta['badge']} {meta['label']}"},
        },
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**用例通过率**\n**{pass_rate}** ({passed}/{total})"},
        },
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**失败 / 错误**\n{failed} / {error}"},
        },
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**执行耗时**\n{duration_str}"},
        },
    ]

    if summary.get("rps") is not None:
        fields.append(
            {
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**TPS / RPS**\n{summary.get('rps')}"},
            }
        )
    if summary.get("p95_ms") is not None:
        fields.append(
            {
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**P95 响应延迟**\n{summary.get('p95_ms')}ms"},
            }
        )

    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "fields": fields,
        },
        {
            "tag": "hr",
        },
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看执行报告"},
                    "type": "primary" if status == "passed" else "danger",
                    "url": url,
                }
            ],
        },
    ]

    return {
        "msgtype": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": meta["feishu_template"],
            },
            "elements": elements,
        },
    }


def compute_feishu_signature(secret: str, timestamp: int) -> str:
    """Generate Feishu webhook HMAC-SHA256 signature."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def sign_feishu_payload(payload: dict[str, Any], secret: str) -> dict[str, Any]:
    """Attach timestamp and sign to a Feishu webhook JSON payload if secret is present."""
    if not secret:
        return payload
    ts = int(time.time())
    sig = compute_feishu_signature(secret, ts)
    new_payload = dict(payload)
    new_payload["timestamp"] = str(ts)
    new_payload["sign"] = sig
    return new_payload
