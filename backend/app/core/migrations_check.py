"""启动期校验 Alembic head 与 DB current revision 是否一致。

best-effort：任何异常都只输出 WARNING，不阻断 FastAPI 启动。生产期望的部署流程是
启动前先执行 `alembic upgrade head`；保留 `APP_AUTO_CREATE_TABLES` 兜底开关，仅在
本地排障时启用。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _alembic_root() -> Path:
    # backend/app/core/migrations_check.py → backend/
    return Path(__file__).resolve().parents[2]


def verify_alembic_head_or_warn() -> None:
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        from app.core.database import sync_engine
    except Exception:
        logger.debug("Alembic check skipped: dependencies unavailable")
        return

    try:
        cfg_path = _alembic_root() / "alembic.ini"
        if not cfg_path.exists():
            logger.debug("Alembic check skipped: alembic.ini not found at %s", cfg_path)
            return
        cfg = Config(str(cfg_path))
        script = ScriptDirectory.from_config(cfg)
        head_rev = script.get_current_head()

        with sync_engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current_rev = ctx.get_current_revision()

        if current_rev is None:
            logger.warning(
                "Alembic check: database has no alembic_version table — "
                "run `alembic upgrade head` before starting (or set APP_AUTO_CREATE_TABLES=true for local-only bootstrap)"
            )
            return
        if current_rev != head_rev:
            logger.warning(
                "Alembic check: DB at revision %s but latest head is %s — run `alembic upgrade head`",
                current_rev,
                head_rev,
            )
            return

        logger.info("Alembic check passed (revision %s)", current_rev)
    except Exception as exc:
        logger.warning("Alembic check failed (non-fatal): %s", exc)
