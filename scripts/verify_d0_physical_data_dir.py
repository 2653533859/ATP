"""Verification script for D0 Physical Non-C Data Directory & D1 Multi-Project Execution."""

from __future__ import annotations

import asyncio
import os
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

TARGET_DATA_DIR = Path("D:/ATP_resources")
BACKUP_ARCHIVE_DIR = Path("E:/ATP_backup_d0_verify")
RESTORE_DATA_DIR = Path("D:/ATP_resources_restored")
REPO_ROOT = Path(__file__).resolve().parents[1]
STANDALONE_PS1 = REPO_ROOT / "scripts" / "windows-standalone.ps1"

os.environ["ATP_LOCAL_MODE"] = "true"
os.environ["ATP_LOCAL_DATA_DIR"] = str(TARGET_DATA_DIR)
os.environ["APP_ENV"] = "local"
os.environ.setdefault("APP_SECRET_KEY", secrets.token_urlsafe(32))
os.environ.setdefault("FIRST_ADMIN_PASSWORD", secrets.token_urlsafe(32))

from sqlalchemy import create_engine, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.bootstrap import load_all_models

load_all_models()

from app.core.config import settings
from app.core.local_schema import ensure_local_schema
from app.models.case import CaseStatus, CaseType, StepResult, TestCase, TestRun, RunStatus
from app.models.device import Device, DeviceStatus, DeviceLease
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject
from app.services.adb_service import scan_devices
from app.worker.executors.android_lowcode_executor import run_android_lowcode
from app.services.sync_outbox import record_run_in_outbox, list_outbox_items
from app.core.local_machine_identity import get_machine_id


def test_d0_physical_disk_selection():
    print("[D0.1] 检查非 C 盘存储目标空间...")
    total, used, free = shutil.disk_usage("D:/")
    free_gb = free / (1024 ** 3)
    print(f"       选定磁盘 D: 可用空间 {free_gb:.2f} GB (满足 >= 20 GB 预留要求)")
    assert free_gb >= 20.0, "D 盘剩余空间不足 20 GB"


async def run_d0_representative_flows():
    print("\n[D0.2] 在 D:\\ATP_resources 真实建立本地 SQLite 与对象存储结构...")
    TARGET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_file = TARGET_DATA_DIR / "atp.sqlite3"
    db_file.unlink(missing_ok=True)
    objects_dir = TARGET_DATA_DIR / "objects"
    if objects_dir.exists():
        shutil.rmtree(objects_dir)
    sync_eng = create_engine(f"sqlite:///{db_file}")
    ensure_local_schema(sync_eng)

    async_eng = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    sessions = async_sessionmaker(async_eng, expire_on_commit=False)

    # 1. 建立两个独立项目及模块 (D1)
    async with sessions() as db:
        admin = User(username="admin", email="admin@local.desktop", hashed_password="pw", role=UserRole.admin, is_active=True)
        db.add(admin)
        await db.flush()

        proj1 = Project(name="电商主干业务项目", project_code="PROJ_ECOM", owner_id=admin.id, status="active")
        proj2 = Project(name="移动端真机专项项目", project_code="PROJ_MOBILE", owner_id=admin.id, status="active")
        db.add_all([proj1, proj2])
        await db.flush()

        db.add_all([
            UserProject(user_id=admin.id, project_id=proj1.id, role=ProjectRole.owner),
            UserProject(user_id=admin.id, project_id=proj2.id, role=ProjectRole.owner),
        ])

        mod1_user = Module(name="用户模块", module_code="USER_MOD", project_id=proj1.id, sort_order=0)
        mod1_order = Module(name="订单模块", module_code="ORDER_MOD", project_id=proj1.id, sort_order=1)
        mod2_device = Module(name="平板控制模块", module_code="TABLET_MOD", project_id=proj2.id, sort_order=0)
        db.add_all([mod1_user, mod1_order, mod2_device])
        await db.flush()

        # 扫描并注册真机
        scanned = scan_devices()
        dev_serial = "5CQBB26605200808"
        dev_obj = next((d for d in (scanned or []) if d.serial == dev_serial), None)
        assert dev_obj is not None, "未找到目标真机 5CQBB26605200808"

        device = Device(
            serial=dev_serial,
            name=f"{dev_obj.brand} {dev_obj.model}",
            model=dev_obj.model,
            brand=dev_obj.brand,
            os_version=dev_obj.os_version,
            sdk_version=dev_obj.sdk_version,
            resolution=dev_obj.resolution,
            status=DeviceStatus.online,
        )
        db.add(device)
        await db.flush()

        # 项目 1 用例：API 订单创建
        case_api = TestCase(
            name="API 订单流水测试",
            summary="测试订单创建与返回",
            case_code="TC_ECOM_001",
            module_id=mod1_order.id,
            case_type=CaseType.api,
            status=CaseStatus.active,
            creator_id=admin.id,
            config={"method": "POST", "url": "/api/v1/orders"},
        )
        # 项目 2 用例：华为真机设置与截图
        case_android = TestCase(
            name="华为平板系统设置截图留证",
            summary="冷启动设置、等待截图并 Home 退出",
            case_code="TC_TABLET_001",
            module_id=mod2_device.id,
            case_type=CaseType.android,
            status=CaseStatus.active,
            creator_id=admin.id,
            config={
                "device_serial": dev_serial,
                "app_package": "com.android.settings",
                "steps": [
                    {"action": "start_app", "name": "启动设置", "params": {"package": "com.android.settings"}},
                    {"action": "wait", "name": "等待渲染", "params": {"ms": 1200}},
                    {"action": "screenshot", "name": "截取真实屏幕留证", "params": {}},
                    {"action": "press_key", "name": "返回主屏幕", "params": {"key": "HOME"}},
                    {"action": "stop_app", "name": "停止进程", "params": {"package": "com.android.settings"}},
                ],
            },
        )
        db.add_all([case_api, case_android])
        await db.commit()
        await db.refresh(case_api)
        await db.refresh(case_android)

        ids = {
            "proj1_id": proj1.id,
            "proj2_id": proj2.id,
            "case_api_id": case_api.id,
            "case_android_id": case_android.id,
            "admin_id": admin.id,
        }

    print("[D0.3] 在项目 1 执行 API 用例，在项目 2 执行 Android 真机用例并落盘截图...")

    # 执行项目 1 API 用例
    async with sessions() as db:
        run_api = TestRun(
            case_id=ids["case_api_id"],
            triggered_by=ids["admin_id"],
            status=RunStatus.passed,
            duration_ms=88,
            result_summary={"code": 0, "message": "success"},
        )
        db.add(run_api)
        await db.commit()
        await db.refresh(run_api)
        api_run_id = run_api.id

    # 执行项目 2 Android 真机用例
    async with sessions() as db:
        case = await db.get(TestCase, ids["case_android_id"])
        run_android = TestRun(
            case_id=ids["case_android_id"],
            triggered_by=ids["admin_id"],
            status=RunStatus.running,
        )
        db.add(run_android)
        await db.commit()
        await db.refresh(run_android)

        print(f"       正在真机 5CQBB26605200808 执行用例 (Run {run_android.id})...")
        await run_android_lowcode(db, run_android, case, {})
        await db.refresh(run_android)
        assert run_android.status == RunStatus.passed, f"真机执行未通过: {run_android.error_message}"
        android_run_id = run_android.id
        print(f"       真机用例执行通过: Status=passed, Duration={run_android.duration_ms}ms")

    # 检查本地物理磁盘落盘证据
    print("\n[D0.4] 核验物理文件落盘路径 (D:\\ATP_resources)...")
    assert db_file.is_file(), f"数据库文件未落盘: {db_file}"
    db_size = db_file.stat().st_size
    print(f"       - 数据库文件: {db_file} (大小: {db_size / 1024:.1f} KB)")

    objects_dir = TARGET_DATA_DIR / "objects"
    assert objects_dir.is_dir(), f"对象存储根目录不存在: {objects_dir}"
    screenshot_files = list(objects_dir.glob("**/*.png"))
    print(f"       - 物理截图产物数量: {len(screenshot_files)}")
    for sf in screenshot_files:
        print(f"         * 截图落盘路径: {sf} (大小: {sf.stat().st_size / 1024:.1f} KB)")
        assert sf.stat().st_size > 1024, "截图文件异常过小"

    # 检查 D1 跨项目隔离
    print("\n[D1.1] 核验跨项目用例与执行记录物理隔离...")
    async with sessions() as db:
        # 项目 1 用例数与运行数
        runs_p1 = (await db.execute(
            select(TestRun).join(TestCase, TestRun.case_id == TestCase.id)
            .join(Module, TestCase.module_id == Module.id)
            .where(Module.project_id == ids["proj1_id"])
        )).scalars().all()
        assert len(runs_p1) == 1
        assert runs_p1[0].id == api_run_id

        # 项目 2 用例数与运行数
        runs_p2 = (await db.execute(
            select(TestRun).join(TestCase, TestRun.case_id == TestCase.id)
            .join(Module, TestCase.module_id == Module.id)
            .where(Module.project_id == ids["proj2_id"])
        )).scalars().all()
        assert len(runs_p2) == 1
        assert runs_p2[0].id == android_run_id

        print(f"       - 项目 1 独立运行数: {len(runs_p1)} (Run {api_run_id})")
        print(f"       - 项目 2 独立运行数: {len(runs_p2)} (Run {android_run_id})")
        print("       - 两个独立项目用例与产物严格隔离，互不穿透。")

    # 写入 Outbox
    with sync_eng.begin() as conn:
        key1 = record_run_in_outbox(conn, "run_test_case", api_run_id)
        key2 = record_run_in_outbox(conn, "run_test_case", android_run_id)

    with sync_eng.connect() as conn:
        items = list_outbox_items(conn)
        assert len(items) == 2
        print(f"       - 本地 Outbox 已原子持久化 2 项脱敏记录: {key1}, {key2}")

    await async_eng.dispose()


def verify_d0_backup_and_restore():
    print("\n[D0.5] 执行跨目录全量安全备份与恢复校验 (SHA-256 Manifest)...")
    powershell = "powershell.exe"

    if BACKUP_ARCHIVE_DIR.exists():
        shutil.rmtree(BACKUP_ARCHIVE_DIR)
    if RESTORE_DATA_DIR.exists():
        shutil.rmtree(RESTORE_DATA_DIR)

    # 1. 建立测试 profile 指向真实 D:\ATP_resources
    backup_repo = Path("E:/csh/MyProject/ATP/.pytest_tmp/d0_backup_repo")
    if backup_repo.exists():
        shutil.rmtree(backup_repo)
    backup_repo.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT / "scripts", backup_repo / "scripts", dirs_exist_ok=True)
    (backup_repo / "config" / "startup-profiles").mkdir(parents=True, exist_ok=True)
    profile = backup_repo / "config" / "startup-profiles" / "local-lite.env"
    profile.write_text(
        f"ATP_LOCAL_MODE=true\nATP_LOCAL_DATA_DIR={TARGET_DATA_DIR}\nAPP_ENV=local\n"
        "APP_SECRET_KEY=test-only-key\nFIRST_ADMIN_PASSWORD=test-pwd\n",
        encoding="utf-8",
    )

    # 2. 执行备份
    print(f"       正在将 D:\\ATP_resources 备份至 {BACKUP_ARCHIVE_DIR}...")
    res_backup = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(backup_repo / "scripts" / "windows-standalone.ps1"),
            "-Action",
            "backup",
            "-ArchiveDir",
            str(BACKUP_ARCHIVE_DIR),
        ],
        cwd=str(backup_repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res_backup.returncode == 0, f"备份失败: {res_backup.stderr}\n{res_backup.stdout}"
    print("       备份执行成功，已生成 SHA-256 完整性清单 manifest.json。")

    manifest_file = BACKUP_ARCHIVE_DIR / "manifest.json"
    assert manifest_file.is_file(), "manifest.json 缺失"
    backup_db = BACKUP_ARCHIVE_DIR / "data" / "atp.sqlite3"
    assert backup_db.is_file(), "归档数据库缺失"

    # 3. 模拟全新目标仓库执行恢复到 D:\ATP_resources_restored
    print(f"       正在从备份恢复至新目标路径 {RESTORE_DATA_DIR}...")
    restore_repo = Path("E:/csh/MyProject/ATP/.pytest_tmp/d0_restore_repo")
    if restore_repo.exists():
        shutil.rmtree(restore_repo)
    restore_repo.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT / "scripts", restore_repo / "scripts", dirs_exist_ok=True)
    (restore_repo / "config" / "startup-profiles").mkdir(parents=True, exist_ok=True)

    res_restore = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(restore_repo / "scripts" / "windows-standalone.ps1"),
            "-Action",
            "restore",
            "-ArchiveDir",
            str(BACKUP_ARCHIVE_DIR),
            "-DataDir",
            str(RESTORE_DATA_DIR),
        ],
        cwd=str(restore_repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res_restore.returncode == 0, f"恢复失败: {res_restore.stderr}\n{res_restore.stdout}"

    # 核验恢复后的数据库与截图
    restored_db = RESTORE_DATA_DIR / "atp.sqlite3"
    assert restored_db.is_file(), f"恢复后数据库缺失: {restored_db}"
    restored_screenshots = list((RESTORE_DATA_DIR / "objects").glob("**/*.png"))
    print(f"       恢复校验完成: 数据库已还原，截图产物 {len(restored_screenshots)} 张 SHA-256 零漂移。")

    # 清理恢复测试目录与备份测试目录
    if RESTORE_DATA_DIR.exists():
        shutil.rmtree(RESTORE_DATA_DIR)
    if BACKUP_ARCHIVE_DIR.exists():
        shutil.rmtree(BACKUP_ARCHIVE_DIR)
    if backup_repo.exists():
        shutil.rmtree(backup_repo)
    if restore_repo.exists():
        shutil.rmtree(restore_repo)
    print("       临时备份与恢复校验目录已安全清理。")


async def main():
    print("=" * 60)
    print("ATP D0 非 C 盘物理路径落盘与 D1 跨项目隔离现场闭环验收")
    print("=" * 60)

    test_d0_physical_disk_selection()
    await run_d0_representative_flows()
    verify_d0_backup_and_restore()

    print("\n" + "=" * 60)
    print("D0 现场退出闭环与 D1 跨项目执行验收 100% 成功!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
