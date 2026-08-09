"""Maintenance tasks for the iOS/Appium worker boundary."""

from app.core.database import AsyncSessionLocal
from app.worker.async_runner import run_async
from app.worker.celery_app import celery_app


@celery_app.task(name="reclaim_expired_ios_device_leases")
def reclaim_expired_ios_device_leases():
    async def _run():
        from app.services.ios_device_leases import reclaim_expired_ios_device_leases as reclaim

        async with AsyncSessionLocal() as db:
            count = await reclaim(db)
            await db.commit()
            return count

    return run_async(_run())
