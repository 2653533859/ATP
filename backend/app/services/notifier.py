"""
通知发送服务

支持三种渠道：
- email:    SMTP 邮件
- wechat:   企业微信机器人 Webhook
- dingtalk:  钉钉机器人 Webhook
"""

import hashlib
import hmac
import base64
import json
import logging
import smtplib
import time
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from smtplib import SMTP

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import decrypt_config
from app.models.notification import NotificationConfig, NotifyChannel

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {"zh-CN", "en-US"}

LABELS = {
    "zh-CN": {
        "default_title": "ATP 测试执行完成",
        "email_title": "测试执行完成",
        "status": "状态",
        "passed": "通过",
        "failed": "失败",
        "error": "错误",
        "duration": "耗时",
        "trigger": "触发",
        "performance": {
            "rps": "请求速率",
            "p95_ms": "P95 延迟",
            "p99_ms": "P99 延迟",
            "error_rate": "错误率",
            "threshold": "阈值",
            "reasons": "触发原因",
            "threshold_statuses": {
                "passed": "通过",
                "failed": "失败",
                "not_configured": "未配置",
                "pending": "等待",
                "cancelled": "已取消",
            },
            "reasons_map": {
                "run_failed": "运行失败",
                "threshold_failed": "阈值失败",
                "baseline_regression": "基线回归",
                "node_issue": "节点异常",
                "resource_issue": "资源采样异常",
            },
        },
        "statuses": {"passed": "通过", "failed": "失败", "error": "异常"},
        "triggers": {"manual": "手动", "cron": "定时", "webhook": "Webhook"},
    },
    "en-US": {
        "default_title": "ATP test execution completed",
        "email_title": "Test execution completed",
        "status": "Status",
        "passed": "Passed",
        "failed": "Failed",
        "error": "Errors",
        "duration": "Duration",
        "trigger": "Trigger",
        "performance": {
            "rps": "RPS",
            "p95_ms": "P95 latency",
            "p99_ms": "P99 latency",
            "error_rate": "Error rate",
            "threshold": "Threshold",
            "reasons": "Reasons",
            "threshold_statuses": {
                "passed": "Passed",
                "failed": "Failed",
                "not_configured": "Not configured",
                "pending": "Pending",
                "cancelled": "Cancelled",
            },
            "reasons_map": {
                "run_failed": "Run failed",
                "threshold_failed": "Threshold failed",
                "baseline_regression": "Baseline regression",
                "node_issue": "Node issue",
                "resource_issue": "Resource sampling issue",
            },
        },
        "statuses": {"passed": "Passed", "failed": "Failed", "error": "Error"},
        "triggers": {"manual": "Manual", "cron": "Scheduled", "webhook": "Webhook"},
    },
}


async def send_notifications(
    db: AsyncSession,
    project_id: int,
    summary: dict,
    report_html: str | None = None,
):
    """
    向项目所有启用的通知渠道发送执行结果摘要。

    summary 结构:
    {
        "title": "测试计划 XXX 执行完成",
        "status": "passed" | "failed" | "error",
        "total": 5,
        "passed": 3,
        "failed": 1,
        "error": 1,
        "duration_ms": 12345,
        "trigger_type": "manual" | "cron" | "webhook",
    }

    report_html: 可选 HTML 报告正文；当某个 email 配置中 attach_html_report=True 时作为邮件正文。
    """
    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.project_id == project_id,
            NotificationConfig.is_enabled == True,  # noqa: E712
        )
    )
    configs = result.scalars().all()

    for cfg in configs:
        try:
            real_config = decrypt_config(cfg.config)
            if not should_send_notification(real_config, summary):
                continue
            if cfg.channel == NotifyChannel.email:
                email_html = report_html if real_config.get("attach_html_report") else None
                await _send_email(real_config, summary, html_body=email_html)
            elif cfg.channel == NotifyChannel.wechat:
                await _send_wechat(real_config, summary)
            elif cfg.channel == NotifyChannel.dingtalk:
                await _send_dingtalk(real_config, summary)
        except Exception as e:
            logger.error(f"通知发送失败 [{cfg.channel.value}] config_id={cfg.id}: {e}")


async def email_html_report_enabled(db: AsyncSession, project_id: int) -> bool:
    """快速检查项目是否有任何启用了 attach_html_report 的邮件通知配置。

    调用方据此决定是否提前生成 HTML 报告（避免无配置时浪费 CPU/IO）。
    """
    result = await db.execute(
        select(NotificationConfig).where(
            NotificationConfig.project_id == project_id,
            NotificationConfig.is_enabled == True,  # noqa: E712
            NotificationConfig.channel == NotifyChannel.email,
        )
    )
    for cfg in result.scalars().all():
        try:
            real_config = decrypt_config(cfg.config)
            if real_config.get("attach_html_report"):
                return True
        except Exception:
            continue
    return False


def _normalize_language(language: str | None) -> str:
    return language if language in SUPPORTED_LANGUAGES else "zh-CN"


def _labels(language: str | None) -> dict:
    return LABELS[_normalize_language(language)]


def _to_int_set(value) -> set[int]:
    if not isinstance(value, list):
        return set()
    result: set[int] = set()
    for item in value:
        try:
            result.add(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _to_str_set(value) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if item is not None}


def should_send_notification(config: dict, summary: dict) -> bool:
    """Return whether a channel config matches this execution summary."""
    status_filters = _to_str_set(config.get("status_filters"))
    if status_filters and str(summary.get("status")) not in status_filters:
        return False

    scope = config.get("scope", "all")
    entity_type = summary.get("entity_type")

    if scope == "suites":
        if entity_type != "suite":
            return False
        suite_ids = _to_int_set(config.get("suite_ids"))
        return not suite_ids or int(summary.get("suite_id") or 0) in suite_ids

    if scope == "plans":
        if entity_type != "plan":
            return False
        plan_ids = _to_int_set(config.get("plan_ids"))
        return not plan_ids or int(summary.get("plan_id") or 0) in plan_ids

    return True


def _localized_value(labels: dict, group: str, value: str | None) -> str:
    if not value:
        return "-"
    return labels.get(group, {}).get(value, value)


def _format_metric(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:g}"
    return str(value)


def _format_error_rate(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value * 100:.2f}%"
    return _format_metric(value)


def _performance_notification_fields(summary: dict, labels: dict) -> list[tuple[str, str]]:
    """Add performance metrics and operational reasons without changing generic notifications."""

    if summary.get("entity_type") != "performance":
        return []

    performance_labels = labels["performance"]
    fields: list[tuple[str, str]] = []
    if summary.get("rps") is not None:
        fields.append((performance_labels["rps"], _format_metric(summary["rps"])))
    if summary.get("p95_ms") is not None:
        fields.append((performance_labels["p95_ms"], f"{_format_metric(summary['p95_ms'])}ms"))
    if summary.get("p99_ms") is not None:
        fields.append((performance_labels["p99_ms"], f"{_format_metric(summary['p99_ms'])}ms"))
    if summary.get("error_rate") is not None:
        fields.append((performance_labels["error_rate"], _format_error_rate(summary["error_rate"])))

    threshold_status = summary.get("threshold_status")
    if threshold_status:
        threshold_text = performance_labels["threshold_statuses"].get(threshold_status, threshold_status)
        fields.append((performance_labels["threshold"], threshold_text))

    reasons = summary.get("performance_event_reasons")
    if isinstance(reasons, list) and reasons:
        reason_text = [performance_labels["reasons_map"].get(str(reason), str(reason)) for reason in reasons]
        fields.append((performance_labels["reasons"], ", ".join(reason_text)))
    return fields


def _build_text(summary: dict, language: str = "zh-CN") -> str:
    """构建纯文本通知内容"""
    labels = _labels(language)
    status_emoji = {"passed": "✅", "failed": "❌", "error": "⚠️"}.get(summary.get("status", ""), "")
    duration = summary.get("duration_ms", 0)
    duration_str = f"{duration / 1000:.1f}s" if duration else "-"
    status = _localized_value(labels, "statuses", summary.get("status"))
    trigger = _localized_value(labels, "triggers", summary.get("trigger_type"))

    lines = [
        f"{status_emoji} {summary.get('title', labels['default_title'])}",
        f"",
        f"{labels['status']}: {status}",
        f"{labels['passed']}: {summary.get('passed', 0)} / {summary.get('total', 0)}",
        f"{labels['failed']}: {summary.get('failed', 0)}",
        f"{labels['error']}: {summary.get('error', 0)}",
        f"{labels['duration']}: {duration_str}",
        f"{labels['trigger']}: {trigger}",
    ]
    lines.extend(f"{label}: {value}" for label, value in _performance_notification_fields(summary, labels))
    return "\n".join(lines)


def _build_markdown(summary: dict, language: str = "zh-CN") -> str:
    """构建 Markdown 通知内容（用于企业微信/钉钉）"""
    labels = _labels(language)
    status_emoji = {"passed": "✅", "failed": "❌", "error": "⚠️"}.get(summary.get("status", ""), "")
    duration = summary.get("duration_ms", 0)
    duration_str = f"{duration / 1000:.1f}s" if duration else "-"
    status = _localized_value(labels, "statuses", summary.get("status"))
    trigger = _localized_value(labels, "triggers", summary.get("trigger_type"))

    lines = [
        f"### {status_emoji} {summary.get('title', labels['default_title'])}",
        f"> **{labels['status']}**: {status}",
        f"> **{labels['passed']}**: {summary.get('passed', 0)} / {summary.get('total', 0)}",
        f"> **{labels['failed']}**: {summary.get('failed', 0)}  **{labels['error']}**: {summary.get('error', 0)}",
        f"> **{labels['duration']}**: {duration_str}",
        f"> **{labels['trigger']}**: {trigger}",
    ]
    lines.extend(f"> **{label}**: {value}" for label, value in _performance_notification_fields(summary, labels))
    return "\n".join(lines)


async def _send_email(config: dict, summary: dict, html_body: str | None = None):
    """通过 SMTP 发送邮件通知。

    html_body 存在时，邮件以 HTML 为主、纯文本摘要作为 alternative；
    否则仅发送纯文本（兼容历史行为）。
    """
    recipients = config.get("recipients", [])
    if not recipients:
        return

    language = _normalize_language(config.get("language"))
    labels = _labels(language)
    subject_prefix = config.get("subject_prefix", "[ATP]")
    status = summary.get("status", "unknown")
    subject = f"{subject_prefix} {summary.get('title', labels['email_title'])} - {status.upper()}"

    text_body = _build_text(summary, language)

    if html_body:
        # 使用 multipart/alternative：客户端优先 HTML，纯文本作降级
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(text_body, "plain", "utf-8"))

    # 在线程池中执行同步 SMTP 操作
    import asyncio

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _smtp_send, msg, recipients)


def _smtp_send(msg: MIMEMultipart, recipients: list[str]):
    """同步 SMTP 发送"""
    try:
        server: SMTP
        if settings.SMTP_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            if settings.SMTP_TLS:
                server.starttls()

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM, recipients, msg.as_string())
        server.quit()
        logger.info(f"邮件通知发送成功 -> {recipients}")
    except Exception as e:
        logger.error(f"SMTP 发送失败: {e}")
        raise


async def _send_wechat(config: dict, summary: dict):
    """通过企业微信机器人 Webhook 发送通知"""
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": _build_markdown(summary, _normalize_language(config.get("language"))),
        },
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(webhook_url, json=payload)
        if resp.status_code != 200:
            message = f"企业微信请求失败: HTTP {resp.status_code}"
            logger.error(message)
            raise RuntimeError(message)

        data = resp.json()
        if data.get("errcode") != 0:
            logger.error(f"企业微信通知失败: {data}")
            raise RuntimeError(data.get("errmsg") or str(data))

        logger.info("企业微信通知发送成功")


async def _send_dingtalk(config: dict, summary: dict):
    """通过钉钉机器人 Webhook 发送通知（支持签名验证）"""
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return

    secret = config.get("secret", "")

    # 钉钉签名
    if secret:
        timestamp = str(int(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": summary.get("title", _labels(config.get("language"))["default_title"]),
            "text": _build_markdown(summary, _normalize_language(config.get("language"))),
        },
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(webhook_url, json=payload)
        if resp.status_code != 200:
            message = f"钉钉请求失败: HTTP {resp.status_code}"
            logger.error(message)
            raise RuntimeError(message)

        data = resp.json()
        if data.get("errcode") != 0:
            logger.error(f"钉钉通知失败: {data}")
            raise RuntimeError(data.get("errmsg") or str(data))

        logger.info("钉钉通知发送成功")
