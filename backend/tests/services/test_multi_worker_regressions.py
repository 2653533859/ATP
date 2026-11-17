"""Phase 0 关键回归场景：同 serial 跨节点隔离与长任务期间独立心跳。

在 Phase 1 / Phase 2 落地前以 xfail(strict=True) 守住契约目标；
对应阶段完成后必须移除 xfail 标记使其作为常规回归长期运行。
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceStatus
from app.services.adb_service import AdbDeviceInfo
from app.services.device_sync import sync_devices_to_db_sync

load_all_models()


def test_same_serial_across_two_workers_coexists_and_isolates_offline():
    """两台主机同时接入 emulator-5554 时应各自独立存在，互不覆盖离线状态。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        sync_devices_to_db_sync(
            session,
            [AdbDeviceInfo(serial="emulator-5554", status="device", model="Pixel-A")],
            worker_id="android-win-a",
            worker_hostname="HOST-A",
        )
        session.commit()

        sync_devices_to_db_sync(
            session,
            [AdbDeviceInfo(serial="emulator-5554", status="device", model="Pixel-B")],
            worker_id="android-win-b",
            worker_hostname="HOST-B",
        )
        session.commit()

        devices = session.scalars(select(Device).order_by(Device.id)).all()
        assert len(devices) == 2
        assert {(d.worker_id, d.serial, d.status) for d in devices} == {
            ("android-win-a", "emulator-5554", DeviceStatus.online),
            ("android-win-b", "emulator-5554", DeviceStatus.online),
        }

        # 主机 A 拔掉设备后扫描为空，不应把主机 B 的同名设备标为 offline
        sync_devices_to_db_sync(
            session,
            [],
            worker_id="android-win-a",
            worker_hostname="HOST-A",
        )
        session.commit()

        by_worker = {d.worker_id: d for d in session.scalars(select(Device)).all()}
        assert by_worker["android-win-a"].status == DeviceStatus.offline
        assert by_worker["android-win-b"].status == DeviceStatus.online


def test_worker_heartbeat_continues_while_long_task_blocks_execution_slot():
    """模拟 solo 执行槽被长任务阻塞时，独立心跳守护线程仍应持续刷新注册状态。"""
    from app.services import android_worker_registry as registry

    assert hasattr(registry, "AndroidWorkerHeartbeatThread"), "缺少独立心跳守护线程实现"
    ticks: list[float] = []

    class FakeClient:
        def set(self, *args, **kwargs):
            ticks.append(time.monotonic())
            return True

        def delete(self, *args, **kwargs):
            return 1

    hb = registry.AndroidWorkerHeartbeatThread(
        worker_id="android-win-a",
        instance_token="tok-1",
        instance_generation=1,
        interval_seconds=0.05,
        ttl_seconds=1.0,
        redis_client=FakeClient(),
    )
    hb.start()
    try:
        # 阻塞当前线程模拟 solo 执行槽执行长任务
        time.sleep(0.18)
    finally:
        hb.stop()

    assert len(ticks) >= 2
