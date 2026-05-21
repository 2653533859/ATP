"""PostgreSQL 自动备份 Celery 任务（F.2）。

策略：
- daily：每日凌晨执行 pg_dump → 上传 MinIO 前缀 `pg-backups/daily/`
- weekly：每周一执行，前缀 `pg-backups/weekly/`
- 保留：daily 保留最近 N 天（DB_BACKUP_RETAIN_DAILY），weekly 保留最近 M 份

实现方式：调用 `scripts/backup-postgres.sh`（容器内安装 pg_dump + mc 即可），失败抛出异常由 Celery 重试。
若运维侧未启用（DB_BACKUP_ENABLED=False），任务直接 noop 返回。
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    from celery.utils.log import get_task_logger
    logger = get_task_logger(__name__)
except Exception:  # 测试环境未装 celery 时退化为标准 logger
    logger = logging.getLogger(__name__)

from app.core.config import settings
from app.worker.celery_app import celery_app

_BACKUP_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "backup-postgres.sh"


def _run_backup_script(kind: str) -> dict:
    """同步调用备份脚本，返回 stdout/stderr/code。"""
    if not _BACKUP_SCRIPT.exists():
        raise FileNotFoundError(f"backup script missing: {_BACKUP_SCRIPT}")
    env = {"BACKUP_KIND": kind}
    proc = subprocess.run(
        ["sh", str(_BACKUP_SCRIPT)],
        env={**__import__("os").environ, **env},
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return {"code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _list_backup_objects(prefix: str) -> list[str]:
    """列出 MinIO 中指定前缀的备份对象，缺包时返回空 list。"""
    try:
        from app.core.minio_client import list_objects
    except Exception as exc:
        logger.warning("list_objects unavailable: %s", exc)
        return []
    try:
        objs = list_objects(prefix=prefix)
    except Exception as exc:
        logger.warning("list_objects failed for %s: %s", prefix, exc)
        return []
    names: list[str] = []
    for obj in objs or []:
        name = getattr(obj, "object_name", None) or getattr(obj, "name", None)
        if name:
            names.append(name)
    return names


_TS_PATTERN = re.compile(r"atp-(\d{8})-(\d{6})\.sql\.gz$")


def _parse_backup_timestamp(name: str) -> datetime | None:
    m = _TS_PATTERN.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _select_to_delete(objects: list[str], keep: int) -> list[str]:
    """按时间戳排序，保留最近 keep 个，返回其余对象名。"""
    parsed = [(name, _parse_backup_timestamp(name)) for name in objects]
    valid = [(name, ts) for name, ts in parsed if ts is not None]
    valid.sort(key=lambda item: item[1], reverse=True)
    if len(valid) <= keep:
        return []
    return [name for name, _ts in valid[keep:]]


def _delete_objects(names: list[str]) -> int:
    if not names:
        return 0
    try:
        from app.core.minio_client import delete_file
    except Exception as exc:
        logger.warning("delete_file unavailable: %s", exc)
        return 0
    deleted = 0
    for name in names:
        try:
            delete_file(name)
            deleted += 1
        except Exception as exc:
            logger.warning("delete %s failed: %s", name, exc)
    return deleted


def _enforce_retention(kind: str) -> int:
    prefix = f"{settings.DB_BACKUP_PREFIX}/{kind}/"
    objects = _list_backup_objects(prefix)
    keep = settings.DB_BACKUP_RETAIN_DAILY if kind == "daily" else settings.DB_BACKUP_RETAIN_WEEKLY
    to_delete = _select_to_delete(objects, keep)
    deleted = _delete_objects(to_delete)
    logger.info("retention %s: kept=%d deleted=%d", kind, min(len(objects), keep), deleted)
    return deleted


@celery_app.task(name="backup_postgres_daily", bind=True, max_retries=2, default_retry_delay=300)
def backup_postgres_daily(self) -> dict:
    """每日 pg_dump → MinIO daily 前缀 + 清理超期。"""
    if not settings.DB_BACKUP_ENABLED:
        logger.info("DB_BACKUP_ENABLED=False, skip daily backup")
        return {"skipped": True, "kind": "daily"}

    result = _run_backup_script("daily")
    if result["code"] != 0:
        logger.error("daily backup failed: %s", result["stderr"][:500])
        raise self.retry(exc=RuntimeError(f"backup-postgres.sh exit={result['code']}"))

    deleted = _enforce_retention("daily")
    return {"kind": "daily", "deleted": deleted, "stdout_tail": result["stdout"][-200:]}


@celery_app.task(name="backup_postgres_weekly", bind=True, max_retries=2, default_retry_delay=300)
def backup_postgres_weekly(self) -> dict:
    """每周一 pg_dump → MinIO weekly 前缀 + 清理超期。"""
    if not settings.DB_BACKUP_ENABLED:
        logger.info("DB_BACKUP_ENABLED=False, skip weekly backup")
        return {"skipped": True, "kind": "weekly"}

    result = _run_backup_script("weekly")
    if result["code"] != 0:
        logger.error("weekly backup failed: %s", result["stderr"][:500])
        raise self.retry(exc=RuntimeError(f"backup-postgres.sh exit={result['code']}"))

    deleted = _enforce_retention("weekly")
    return {"kind": "weekly", "deleted": deleted, "stdout_tail": result["stdout"][-200:]}
