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
        "statuses": {"passed": "Passed", "failed": "Failed", "error": "Error"},
        "triggers": {"manual": "Manual", "cron": "Scheduled", "webhook": "Webhook"},
    },
}


async def send_notifications(db: AsyncSession, project_id: int, summary: dict):
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
            if cfg.channel == NotifyChannel.email:
                await _send_email(real_config, summary)
            elif cfg.channel == NotifyChannel.wechat:
                await _send_wechat(real_config, summary)
            elif cfg.channel == NotifyChannel.dingtalk:
                await _send_dingtalk(real_config, summary)
        except Exception as e:
            logger.error(f"通知发送失败 [{cfg.channel.value}] config_id={cfg.id}: {e}")


def _normalize_language(language: str | None) -> str:
    return language if language in SUPPORTED_LANGUAGES else "zh-CN"


def _labels(language: str | None) -> dict:
    return LABELS[_normalize_language(language)]


def _localized_value(labels: dict, group: str, value: str | None) -> str:
    if not value:
        return "-"
    return labels.get(group, {}).get(value, value)


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
    return "\n".join(lines)


async def _send_email(config: dict, summary: dict):
    """通过 SMTP 发送邮件通知"""
    recipients = config.get("recipients", [])
    if not recipients:
        return

    language = _normalize_language(config.get("language"))
    labels = _labels(language)
    subject_prefix = config.get("subject_prefix", "[ATP]")
    status = summary.get("status", "unknown")
    subject = f"{subject_prefix} {summary.get('title', labels['email_title'])} - {status.upper()}"

    body = _build_text(summary, language)

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # 在线程池中执行同步 SMTP 操作
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _smtp_send, msg, recipients)


def _smtp_send(msg: MIMEMultipart, recipients: list[str]):
    """同步 SMTP 发送"""
    try:
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
