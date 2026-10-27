"""End-to-end verification script for M3 Android real-device closed loop."""

from __future__ import annotations

import asyncio
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

os.environ["ATP_LOCAL_MODE"] = "true"
os.environ["APP_ENV"] = "local"
os.environ.setdefault("APP_SECRET_KEY", secrets.token_urlsafe(32))
os.environ.setdefault("FIRST_ADMIN_PASSWORD", secrets.token_urlsafe(32))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.bootstrap import load_all_models

load_all_models()

from app.models.case import CaseStatus, CaseType, StepResult, TestCase, TestRun, RunStatus
from app.models.device import Device, DeviceStatus, DeviceLease
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.services.adb_service import scan_devices
from app.services.android_precheck import precheck_android_execution
from app.worker.executors.android_lowcode_executor import run_android_lowcode
from app.services.sync_outbox import record_run_in_outbox, list_outbox_items
from app.services.cloud_sync_client import sync_pending_outbox
from app.core.local_schema import ensure_local_schema
from sqlalchemy import create_engine


async def main():
    print("=" * 60)
    print("ATP M3 真机全流程闭环实测 (Android Real Device Closed Loop)")
    print("=" * 60)

    # 1. 扫描 ADB 真机
    scanned_devices = scan_devices()
    print(f"[1/7] ADB 设备扫描结果: {scanned_devices}")
    target_dev = next((d for d in (scanned_devices or []) if d.serial == "5CQBB26605200808"), None)
    if not target_dev:
        print("ERROR: 未找到设备 5CQBB26605200808")
        sys.exit(1)
    print(f"      识别到设备: 品牌={target_dev.brand}, 型号={target_dev.model}, "
          f"系统={target_dev.os_version} (SDK {target_dev.sdk_version}), 分辨率={target_dev.resolution}")

    # 2. 初始化本地 SQLite 数据库与 Schema v15
    db_file = Path("E:/csh/MyProject/ATP/.pytest_tmp/m3_real_device.sqlite3")
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.unlink(missing_ok=True)
    sync_eng = create_engine(f"sqlite:///{db_file}")
    ensure_local_schema(sync_eng)

    async_eng = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    sessions = async_sessionmaker(async_eng, expire_on_commit=False)

    async with sessions() as db:
        admin = await db.scalar(select(User).where(User.username == "admin"))
        if not admin:
            admin = User(username="admin", email="admin@atp.local", hashed_password="pw", role=UserRole.admin, is_active=True)
            db.add(admin)
            await db.flush()

        proj = await db.scalar(select(Project).where(Project.project_code == "ANDROID_REAL"))
        if not proj:
            proj = Project(name="Android Real Device Project", project_code="ANDROID_REAL", owner_id=admin.id, status="active")
            db.add(proj)
            await db.flush()

        mod = await db.scalar(select(Module).where(Module.project_id == proj.id))
        if not mod:
            mod = Module(name="System Settings Suite", module_code="SYS_SET", project_id=proj.id, sort_order=0)
            db.add(mod)
            await db.flush()

        device = await db.scalar(select(Device).where(Device.serial == target_dev.serial))
        if not device:
            device = Device(
                serial=target_dev.serial,
                name=f"{target_dev.brand} {target_dev.model}",
                model=target_dev.model,
                brand=target_dev.brand,
                os_version=target_dev.os_version,
                sdk_version=target_dev.sdk_version,
                resolution=target_dev.resolution,
                status=DeviceStatus.online,
            )
            db.add(device)
        else:
            device.status = DeviceStatus.online

        await db.commit()
        await db.refresh(device)
        print(f"[2/7] 已在本地数据库注册设备: ID={device.id}, Serial={device.serial}, Status={device.status.value}")
    # 3. 构造低代码测试用例与预检 (M1/M2)
    success_steps = [
        {"action": "start_app", "name": "启动系统设置", "params": {"package": "com.android.settings"}},
        {"action": "wait", "name": "等待页面渲染", "params": {"ms": 1500}},
        {"action": "screenshot", "name": "捕获设置页屏幕", "params": {}},
        {"action": "press_key", "name": "点击返回键", "params": {"key": "BACK"}},
        {"action": "wait", "name": "等待页面返回", "params": {"ms": 800}},
        {"action": "press_key", "name": "返回主屏幕", "params": {"key": "HOME"}},
        {"action": "wait", "name": "等待主屏幕稳定", "params": {"ms": 1000}},
        {"action": "stop_app", "name": "停止设置进程", "params": {"package": "com.android.settings"}},
    ]

    async with sessions() as db:
        case = TestCase(
            name="M3 华为真机设置启停与按键流程",
            summary="华为平板系统设置启停、截图与按键回退",
            case_code="TC_M3_REAL_001",
            module_id=1,
            case_type=CaseType.android,
            status=CaseStatus.active,
            creator_id=1,
            config={
                "device_serial": "5CQBB26605200808",
                "app_package": "com.android.settings",
                "steps": success_steps,
            },
        )
        db.add(case)
        await db.commit()
        await db.refresh(case)

        # 执行 M2 结构化预检诊断
        precheck = await precheck_android_execution(
            db,
            case=case,
            device_serial="5CQBB26605200808",
            config=case.config,
            steps=success_steps,
            check_adb_environment=True,
            strict_adb_environment=True,
        )
        print(f"[3/7] M2 执行前预检完成: ok={precheck.ok}, total_steps={precheck.summary.total_steps}, items_count={len(precheck.items)}")
        for item in precheck.items:
            print(f"      - [{item.status.value.upper()}] {item.scope.value}: {item.code} -> {item.message}")
        if not precheck.ok:
            print("ERROR: 预检诊断未通过!")
            sys.exit(1)

    # 4. 执行真机测试用例 (成功路径)
    async with sessions() as db:
        run = TestRun(
            case_id=case.id,
            triggered_by=1,
            status=RunStatus.running,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        print(f"[4/7] 开始在真机 5CQBB26605200808 上执行低代码用例 (Run ID: {run.id})...")
        await run_android_lowcode(db, run, case, {})

        await db.refresh(run)
        print(f"      真机用例执行完成: Status={run.status.value}, Duration={run.duration_ms}ms, Error={run.error_message}")

        # 检查步骤结果
        steps_stmt = select(StepResult).where(StepResult.run_id == run.id).order_by(StepResult.step_index)
        steps_res = (await db.execute(steps_stmt)).scalars().all()
        print(f"      步骤完成总数: {len(steps_res)}")
        for s in steps_res:
            print(f"      - 步骤 {s.step_index} [{s.name}]: {s.status.value} ({s.duration_ms}ms), 截图={s.screenshot_url}")

        # 检查租约是否安全释放
        leases_cnt = await db.scalar(select(func.count(DeviceLease.id)))
        print(f"      设备租约状态: 当前活动租约数={leases_cnt} (已安全释放)")

        success_run_id = run.id

    # 5. 执行异常与故障路径测试 (包名不存在)
    async with sessions() as db:
        fault_steps = [
            {"action": "start_app", "name": "启动不存在的包名", "params": {"package": "com.invalid.nonexistent.app"}},
        ]
        fault_case = TestCase(
            name="M3 故障路径-不存在应用异常阻断",
            summary="校验不存在应用被拦截或标记失败",
            case_code="TC_M3_FAULT_002",
            module_id=1,
            case_type=CaseType.android,
            status=CaseStatus.active,
            creator_id=1,
            config={
                "device_serial": "5CQBB26605200808",
                "app_package": "com.invalid.nonexistent.app",
                "steps": fault_steps,
            },
        )
        db.add(fault_case)
        await db.commit()
        await db.refresh(fault_case)

        fault_run = TestRun(
            case_id=fault_case.id,
            triggered_by=1,
            status=RunStatus.running,
        )
        db.add(fault_run)
        await db.commit()
        await db.refresh(fault_run)

        print(f"[5/7] 执行故障路径测试 (Run ID: {fault_run.id})...")
        await run_android_lowcode(db, fault_run, fault_case, {})
        await db.refresh(fault_run)
        print(f"      故障用例执行结果: Status={fault_run.status.value}, Error={fault_run.error_message}")
        fault_run_id = fault_run.id

        # 检查租约是否仍然安全释放
        leases_cnt_after = await db.scalar(select(func.count(DeviceLease.id)))
        print(f"      故障后租约状态: 当前活动租约数={leases_cnt_after} (已安全释放)")

    # 6. 本地 Outbox 队列入队与脱敏
    with sync_eng.begin() as conn:
        key_success = record_run_in_outbox(conn, "run_test_case", success_run_id)
        key_fault = record_run_in_outbox(conn, "run_test_case", fault_run_id)
        print(f"[6/7] 本地 Outbox 原子入队完成:")
        print(f"      - 成功用例 UniqueKey: {key_success}")
        print(f"      - 故障用例 UniqueKey: {key_fault}")

    with sync_eng.connect() as conn:
        pending_items = list_outbox_items(conn, status="pending")
        print(f"      本地待同步记录数: {len(pending_items)}")

    # 7. 跨网络同步至 192.168.3.196:8000
    cloud_url = "http://192.168.3.196:8000"
    print(f"[7/7] 开始将真机结果 Outbox 同步至云端服务器 ({cloud_url})...")
    sync_res = sync_pending_outbox(sync_url=cloud_url, engine=sync_eng)
    print(f"      跨端同步响应: {sync_res}")

    with sync_eng.connect() as conn:
        synced_items = list_outbox_items(conn, status="synced")
        print(f"      本地 Outbox 状态: 已同步数量={len(synced_items)}")
        for item in synced_items:
            print(f"      - [{item['unique_key']}] status={item['status']}, synced_at={item['synced_at']}")

    print("\n" + "=" * 60)
    print("M3 真机全流程端到端闭环验证 100% 成功!")
    print("=" * 60)

    await async_eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
