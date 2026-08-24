"""PostgreSQL 自动备份 Celery 任务（F.2）。

策略：
- daily：每日凌晨执行 pg_dump → 上传 MinIO 前缀 `pg-backups/daily/`
- weekly：每周一执行，前缀 `pg-backups/weekly/`
- 保留：daily 保留最近 N 天（DB_BACKUP_RETAIN_DAILY），weekly 保留最近 M 份

实现方式：直接调用容器内的 `pg_dump` 和 Python MinIO SDK，不依赖仓库根目录脚本或额外的 `mc` 二进制；
失败抛出异常由 Celery 重试。根目录 `scripts/backup-postgres.sh` 仍保留给运维主机手工执行。
若运维侧未启用（DB_BACKUP_ENABLED=False），任务直接 noop 返回。
"""

from __future__ import annotations

import gzip
import logging
import os
import re
import shutil
import subprocess
import tempfile
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


def _run_python_backup(kind: str) -> dict:
    """Stream ``pg_dump`` through gzip and upload it with the bundled MinIO SDK.

    The worker image is built from ``backend/`` and therefore cannot see the
    repository-root shell script. Keeping the runtime path inside Python also
    avoids requiring the mutable ``mc`` CLI in every deployment.
    """

    if kind not in {"daily", "weekly"}:
        raise ValueError(f"unsupported backup kind: {kind}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    object_name = f"{settings.DB_BACKUP_PREFIX}/{kind}/atp-{timestamp}.sql.gz"
    temporary_path = ""
    process = None
    try:
        with tempfile.NamedTemporaryFile(prefix="atp-pg-backup-", suffix=".sql.gz", delete=False) as output:
            temporary_path = output.name

        env = os.environ.copy()
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD
        process = subprocess.Popen(
            [
                "pg_dump",
                "-h",
                settings.POSTGRES_HOST,
                "-p",
                str(settings.POSTGRES_PORT),
                "-U",
                settings.POSTGRES_USER,
                "-d",
                settings.POSTGRES_DB,
                "--format=plain",
                "--no-owner",
                "--no-acl",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if process.stdout is None or process.stderr is None:
            raise RuntimeError("pg_dump pipes were not created")
        with process.stdout, gzip.open(temporary_path, "wb") as compressed:
            shutil.copyfileobj(process.stdout, compressed, length=1024 * 1024)
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        code = process.wait()
        if code != 0:
            return {"code": code, "stdout": "", "stderr": stderr[-2000:]}

        from app.core.minio_client import upload_file

        upload_file(object_name, temporary_path, content_type="application/gzip")
        size = os.path.getsize(temporary_path)
        return {
            "code": 0,
            "stdout": f"uploaded object={object_name} size={size}B",
            "stderr": stderr,
            "object_name": object_name,
        }
    except OSError as exc:
        return {"code": 127, "stdout": "", "stderr": str(exc)[-2000:]}
    except Exception as exc:
        return {"code": 1, "stdout": "", "stderr": str(exc)[-2000:]}
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


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

    result = _run_python_backup("daily")
    if result["code"] != 0:
        logger.error("daily backup failed: %s", result["stderr"][:500])
        raise self.retry(exc=RuntimeError(f"PostgreSQL backup exit={result['code']}"))

    deleted = _enforce_retention("daily")
    return {"kind": "daily", "deleted": deleted, "stdout_tail": result["stdout"][-200:]}


@celery_app.task(name="backup_postgres_weekly", bind=True, max_retries=2, default_retry_delay=300)
def backup_postgres_weekly(self) -> dict:
    """每周一 pg_dump → MinIO weekly 前缀 + 清理超期。"""
    if not settings.DB_BACKUP_ENABLED:
        logger.info("DB_BACKUP_ENABLED=False, skip weekly backup")
        return {"skipped": True, "kind": "weekly"}

    result = _run_python_backup("weekly")
    if result["code"] != 0:
        logger.error("weekly backup failed: %s", result["stderr"][:500])
        raise self.retry(exc=RuntimeError(f"PostgreSQL backup exit={result['code']}"))

    deleted = _enforce_retention("weekly")
    return {"kind": "weekly", "deleted": deleted, "stdout_tail": result["stdout"][-200:]}
