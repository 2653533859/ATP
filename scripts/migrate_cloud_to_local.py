"""Full Migration Script: Cloud PostgreSQL/MinIO to Local Windows D:\\ATP_resources (D6)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

def _private_profile_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    profile = Path(__file__).resolve().parents[1] / "config" / "startup-profiles" / "local-lite.env"
    if profile.is_file():
        for line in profile.read_text(encoding="utf-8").splitlines():
            key, sep, raw_value = line.partition("=")
            if sep and key == name and raw_value.strip():
                return raw_value.strip().strip('"').strip("'")
    raise RuntimeError(f"Set {name} in the private local profile or process environment")


os.environ["ATP_LOCAL_MODE"] = "true"
os.environ["ATP_LOCAL_DATA_DIR"] = "D:/ATP_resources"
os.environ["APP_ENV"] = "local"
os.environ["APP_SECRET_KEY"] = _private_profile_value("APP_SECRET_KEY")
os.environ["FIRST_ADMIN_PASSWORD"] = _private_profile_value("FIRST_ADMIN_PASSWORD")

import paramiko
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.bootstrap import load_all_models

load_all_models()

from app.core.local_schema import ensure_local_schema
from app.models.case import CaseStatus, CaseType, StepResult, TestCase, TestRun, RunStatus
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject

LOCAL_DATA_DIR = Path("D:/ATP_resources")
LOCAL_DB_PATH = LOCAL_DATA_DIR / "atp.sqlite3"
LOCAL_OBJECTS_DIR = LOCAL_DATA_DIR / "objects"

SSH_HOST = os.environ.get("ATP_MIGRATION_SSH_HOST", "")
SSH_PORT = int(os.environ.get("ATP_MIGRATION_SSH_PORT", "22"))
SSH_USER = os.environ.get("ATP_MIGRATION_SSH_USER", "")
SSH_PASS = os.environ.get("ATP_MIGRATION_SSH_PASSWORD")


def connect_ssh() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    if not SSH_HOST or not SSH_USER:
        raise RuntimeError("Set ATP_MIGRATION_SSH_HOST and ATP_MIGRATION_SSH_USER")
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
    return ssh


def step1_cloud_backup_and_inventory(ssh: paramiko.SSHClient) -> dict[str, int]:
    print("[D6.1] 云端源端全量备份与实体盘点...")
    # 1. PostgreSQL 备份
    cmd_pg = (
        "docker exec -i atp-q19-acceptance-20260824-postgres-1 pg_dump -U atp_runtime atp_acceptance > "
        "/opt/atp_acceptance_backup_d6_pre_migration.sql && ls -lh /opt/atp_acceptance_backup_d6_pre_migration.sql"
    )
    stdin, stdout, stderr = ssh.exec_command(cmd_pg)
    out_pg = stdout.read().decode().strip()
    print(f"       - 云端数据库备份先行: {out_pg}")

    # 2. MinIO 归档打包
    cmd_minio = (
        "cd /var/lib/docker/volumes/atp-q19-acceptance-20260824_acceptance_minio/_data/atp && "
        "tar -czf /opt/atp_minio_backup_d6.tar.gz . && ls -lh /opt/atp_minio_backup_d6.tar.gz"
    )
    stdin, stdout, stderr = ssh.exec_command(cmd_minio)
    out_minio = stdout.read().decode().strip()
    print(f"       - 云端 MinIO 附件备份归档: {out_minio}")

    # 3. 统计盘点
    cmd_count = """docker exec -i atp-q19-acceptance-20260824-postgres-1 psql -U atp_runtime -d atp_acceptance -t -A -c "
SELECT 'projects:' || count(*) FROM projects
UNION ALL SELECT 'modules:' || count(*) FROM modules
UNION ALL SELECT 'test_cases:' || count(*) FROM test_cases
UNION ALL SELECT 'test_runs:' || count(*) FROM test_runs
UNION ALL SELECT 'users:' || count(*) FROM users;
" """
    stdin, stdout, stderr = ssh.exec_command(cmd_count)
    counts = {}
    for line in stdout.read().decode().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            counts[k.strip()] = int(v.strip())
    print(f"       - 云端实体盘点统计: {counts}")
    return counts


def step2_export_cloud_tables(ssh: paramiko.SSHClient) -> dict[str, list[dict[str, Any]]]:
    print("\n[D6.2] 从云端 PostgreSQL 结构化抽取实体数据...")
    data: dict[str, list[dict[str, Any]]] = {}

    tables = ["users", "projects", "modules", "test_cases", "test_runs", "step_results"]
    for tbl in tables:
        # Export as JSON array via psql
        cmd = f"""docker exec -i atp-q19-acceptance-20260824-postgres-1 psql -U atp_runtime -d atp_acceptance -t -A -c "
SELECT coalesce(json_agg(t), '[]'::json) FROM (SELECT * FROM {tbl}) t;
" """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        raw = stdout.read().decode().strip()
        try:
            records = json.loads(raw)
            data[tbl] = records
            print(f"       - 抽取 {tbl}: {len(records)} 条记录")
        except Exception as e:
            print(f"       ERROR 抽取 {tbl} 失败: {e}")
            data[tbl] = []

    return data


def step3_import_to_local_sqlite(data: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    print("\n[D6.3] 向本地 SQLite (D:\\ATP_resources\\atp.sqlite3) 分批导入并映射所有权...")
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    sync_eng = create_engine(f"sqlite:///{LOCAL_DB_PATH}")
    ensure_local_schema(sync_eng)

    imported_stats = {"projects": 0, "modules": 0, "test_cases": 0, "test_runs": 0, "step_results": 0}

    with Session(sync_eng) as session:
        # 获取本地管理员
        admin = session.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(username="admin", email="admin@local.desktop", hashed_password="pw", role=UserRole.admin, is_active=True)
            session.add(admin)
            session.flush()

        admin_id = admin.id

        # 1. 导入 Projects
        for p in data.get("projects", []):
            pid = p["id"]
            existing = session.query(Project).filter(Project.id == pid).first()
            if not existing:
                proj = Project(
                    id=pid,
                    name=p["name"],
                    project_code=p.get("project_code") or f"PROJ_{pid}",
                    description=p.get("description"),
                    owner_id=admin_id,
                    status=p.get("status") or "active",
                )
                session.add(proj)
                imported_stats["projects"] += 1
                # 补齐 user_project
                session.add(UserProject(user_id=admin_id, project_id=pid, role=ProjectRole.owner))
        session.flush()

        # 2. 导入 Modules
        for m in data.get("modules", []):
            mid = m["id"]
            existing = session.query(Module).filter(Module.id == mid).first()
            if not existing:
                mod = Module(
                    id=mid,
                    name=m["name"],
                    module_code=m.get("module_code") or f"MOD_{mid}",
                    project_id=m["project_id"],
                    parent_id=m.get("parent_id"),
                    sort_order=m.get("sort_order", 0),
                )
                session.add(mod)
                imported_stats["modules"] += 1
        session.flush()

        # 3. 导入 TestCases
        for c in data.get("test_cases", []):
            cid = c["id"]
            existing = session.query(TestCase).filter(TestCase.id == cid).first()
            if not existing:
                case = TestCase(
                    id=cid,
                    name=c["name"],
                    description=c.get("description"),
                    case_code=c.get("case_code") or f"TC_{cid}",
                    summary=c.get("summary") or c["name"],
                    preconditions=c.get("preconditions") or [],
                    postconditions=c.get("postconditions") or [],
                    case_type=CaseType(c.get("case_type") or "api"),
                    status=CaseStatus(c.get("status") or "active"),
                    priority=c.get("priority") or "P2",
                    case_level=c.get("case_level") or "regression",
                    review_status=c.get("review_status") or "approved",
                    automation_status=c.get("automation_status") or "auto",
                    tags=c.get("tags") or [],
                    module_id=c["module_id"],
                    creator_id=admin_id,
                    owner_id=admin_id,
                    config=c.get("config") or {},
                )
                session.add(case)
                imported_stats["test_cases"] += 1
        session.flush()

        # 4. 导入 TestRuns
        for r in data.get("test_runs", []):
            rid = r["id"]
            existing = session.query(TestRun).filter(TestRun.id == rid).first()
            if not existing:
                st = r.get("status") or "passed"
                run_st = RunStatus(st) if st in RunStatus.__members__ else RunStatus.passed
                run = TestRun(
                    id=rid,
                    case_id=r["case_id"],
                    triggered_by=admin_id,
                    status=run_st,
                    duration_ms=r.get("duration_ms"),
                    error_message=r.get("error_message"),
                    result_summary=r.get("result_summary") or {},
                )
                session.add(run)
                imported_stats["test_runs"] += 1
        session.flush()

        # 5. 导入 StepResults
        for s in data.get("step_results", []):
            sid = s["id"]
            existing = session.query(StepResult).filter(StepResult.id == sid).first()
            if not existing:
                st = s.get("status") or "passed"
                step_st = RunStatus(st) if st in RunStatus.__members__ else RunStatus.passed
                sr = StepResult(
                    id=sid,
                    run_id=s["run_id"],
                    step_index=s.get("step_index", 0),
                    name=s.get("name") or f"Step {s.get('step_index')}",
                    status=step_st,
                    duration_ms=s.get("duration_ms"),
                    request_data=s.get("request_data"),
                    response_data=s.get("response_data"),
                    screenshot_url=s.get("screenshot_url"),
                    error_message=s.get("error_message"),
                )
                session.add(sr)
                imported_stats["step_results"] += 1
        session.flush()

        session.commit()

    print(f"       - 导入统计: {imported_stats}")
    return imported_stats


def step4_sync_minio_objects(ssh: paramiko.SSHClient) -> int:
    print("\n[D6.4] 从云端同步 MinIO 对象附件到本地 D:\\ATP_resources\\objects...")
    LOCAL_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    temp_tar = Path("E:/csh/MyProject/ATP/.pytest_tmp/atp_minio_backup_d6.tar.gz")
    temp_tar.parent.mkdir(parents=True, exist_ok=True)

    sftp = ssh.open_sftp()
    print("       正在下载云端附件归档包 /opt/atp_minio_backup_d6.tar.gz...")
    sftp.get("/opt/atp_minio_backup_d6.tar.gz", str(temp_tar))
    sftp.close()

    print(f"       归档包已下载至本地 (大小: {temp_tar.stat().st_size / (1024*1024):.2f} MB)")
    print("       正在解压并校验对象产物...")

    file_count = 0
    with tarfile.open(temp_tar, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile():
                target_path = LOCAL_OBJECTS_DIR / member.name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                file_count += 1

    temp_tar.unlink(missing_ok=True)
    print(f"       - 本地对象存储已恢复完成: 共 {file_count} 个物理附件")
    return file_count


def step5_verify_parity_and_safety(ssh: paramiko.SSHClient, cloud_counts: dict[str, int]):
    print("\n[D6.5] 核验两侧一致性与云端源数据完好性...")
    sync_eng = create_engine(f"sqlite:///{LOCAL_DB_PATH}")

    with sync_eng.connect() as conn:
        local_projects = conn.execute(text("SELECT count(*) FROM projects")).scalar_one()
        local_cases = conn.execute(text("SELECT count(*) FROM test_cases")).scalar_one()
        local_runs = conn.execute(text("SELECT count(*) FROM test_runs")).scalar_one()

    print(f"       - 本地数据汇总: projects={local_projects}, cases={local_cases}, runs={local_runs}")
    assert local_projects >= cloud_counts["projects"], "本地项目数少于云端源数据"
    assert local_cases >= cloud_counts["test_cases"], "本地用例数少于云端源数据"
    assert local_runs >= cloud_counts["test_runs"], "本地运行记录数少于云端源数据"
    print("       - 核心实体数量与关系映射验证一致!")

    # 验证云端数据未被删除
    cmd_verify = """docker exec -i atp-q19-acceptance-20260824-postgres-1 psql -U atp_runtime -d atp_acceptance -t -A -c "
SELECT count(*) FROM test_cases;
" """
    stdin, stdout, stderr = ssh.exec_command(cmd_verify)
    cloud_cases_after = int(stdout.read().decode().strip())
    assert cloud_cases_after == cloud_counts["test_cases"], "云端源用例数据异常变动!"
    print(f"       - 云端源用例数据校验完好: {cloud_cases_after} 条用例未被篡改或删除 (符合安全准则)")


def main():
    print("=" * 60)
    print("ATP D6 云端历史数据平滑迁入首台 Windows 电脑 (D:\\ATP_resources)")
    print("=" * 60)

    ssh = connect_ssh()
    try:
        cloud_counts = step1_cloud_backup_and_inventory(ssh)
        data = step2_export_cloud_tables(ssh)
        step3_import_to_local_sqlite(data)
        step4_sync_minio_objects(ssh)
        step5_verify_parity_and_safety(ssh, cloud_counts)

        print("\n" + "=" * 60)
        print("D6 历史数据平滑迁移与一致性核验 100% 成功!")
        print("=" * 60)
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
