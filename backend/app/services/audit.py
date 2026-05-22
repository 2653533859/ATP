"""
审计日志服务

提供 write_audit_log() 辅助函数，在关键业务操作中调用。
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def write_audit_log(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    user_id: int | None = None,
    username: str = "",
    detail: str | None = None,
    ip_address: str = "",
    project_id: int | None = None,
) -> None:
    """写入一条审计日志记录"""
    try:
        log = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            username=username,
            detail=detail,
            ip_address=ip_address,
            project_id=project_id,
        )
        db.add(log)
        await db.flush()
    except Exception:
        logger.warning("Failed to write audit log", exc_info=True)
