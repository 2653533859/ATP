"""
统一日志配置

提供 JSON 结构化日志输出，方便日志收集系统（ELK / Loki）解析。
开发环境输出可读格式，生产环境输出 JSON 格式。
支持通过 LOG_LEVEL 环境变量动态配置日志级别。
每条日志自动附加 trace_id（由 TraceMiddleware 注入）。
"""
import logging
import json
import sys
from datetime import datetime, timezone

from app.core.config import settings
from app.core.tracing import get_trace_id


class JSONFormatter(logging.Formatter):
    """将日志记录格式化为 JSON 行"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        tid = get_trace_id()
        if tid:
            log_entry["trace_id"] = tid
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry, ensure_ascii=False)


class DevFormatter(logging.Formatter):
    """开发环境可读格式，附带 trace_id"""

    def format(self, record: logging.LogRecord) -> str:
        tid = get_trace_id()
        tid_part = f" [{tid}]" if tid else ""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts} {record.levelname:<8s} [{record.name}]{tid_part} {record.getMessage()}"


def _resolve_level() -> int:
    """解析日志级别：优先 LOG_LEVEL 环境变量，否则按 APP_ENV 自动选择"""
    if settings.LOG_LEVEL:
        resolved = getattr(logging, settings.LOG_LEVEL.upper(), None)
        if isinstance(resolved, int):
            return resolved
    return logging.DEBUG if settings.APP_ENV == "development" else logging.INFO


def setup_logging() -> None:
    """初始化全局日志配置，应在应用启动时调用"""
    root = logging.getLogger()
    level = _resolve_level()
    root.setLevel(level)

    formatter: logging.Formatter
    if settings.APP_ENV == "production":
        formatter = JSONFormatter()
    else:
        formatter = DevFormatter()

    if root.handlers:
        for handler in root.handlers:
            handler.setLevel(level)
            handler.setFormatter(formatter)
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # 降低第三方库噪音
    for noisy in ("uvicorn.access", "httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
