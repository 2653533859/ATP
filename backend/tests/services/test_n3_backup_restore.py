"""N3.2 Windows 单机备份清单、校验与异目录恢复回归测试。

覆盖：
1. 完整备份清单（manifest.json）结构与 SHA-256 校验；
2. 坏备份与篡改防护（哈希不匹配、文件缺失、未登记文件、目录穿越非法路径全部被拒绝）；
3. 异目录完整恢复与数据可用性（配置文件回读、SQLite 数据库恢复后可连接可查询）。
"""

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app.core.local_schema import CURRENT_LOCAL_SCHEMA_VERSION, ensure_local_schema
from app.models.bootstrap import load_all_models

load_all_models()


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def _write_manifest(target_dir: Path) -> None:
    root = target_dir.resolve()
    entries = []
    for file_path in target_dir.rglob("*"):
        if file_path.is_file() and file_path.name != "manifest.json":
            rel = str(file_path.relative_to(root)).replace("\\", "/")
            entries.append({"path": rel, "sha256": _sha256(file_path)})
    manifest_data = {"format": 1, "files": entries}
    (target_dir / "manifest.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")


def _assert_manifest(source_dir: Path) -> None:
    manifest_path = source_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("Backup manifest is missing.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != 1:
        raise RuntimeError("Unsupported backup manifest format.")

    listed = set()
    root = source_dir.resolve()
    for entry in manifest.get("files", []):
        rel = entry["path"]
        if rel in listed:
            raise RuntimeError("Backup manifest contains a duplicate path.")
        listed.add(rel)

        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as err:
            raise RuntimeError(f"Backup manifest contains an invalid path: {rel}") from err

        if not candidate.is_file():
            raise RuntimeError(f"Backup file missing: {rel}")
        actual_hash = _sha256(candidate)
        if actual_hash.lower() != str(entry["sha256"]).lower():
            raise RuntimeError(f"Backup checksum mismatch: {rel}")

    for file_path in source_dir.rglob("*"):
        if file_path.is_file():
            rel = str(file_path.relative_to(root)).replace("\\", "/")
            if rel != "manifest.json" and rel not in listed:
                raise RuntimeError(f"Unlisted backup file: {rel}")


# ==================== 1. 有效备份清单与 SHA-256 校验 ====================


def test_valid_backup_manifest_passes_verification(tmp_path):
    backup_dir = tmp_path / "backup-valid"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 模拟数据文件与配置
    (backup_dir / "local-lite.env").write_text("ATP_LOCAL_MODE=true\nAPP_ENV=local\n", encoding="utf-8")
    data_dir = backup_dir / "data"
    data_dir.mkdir()
    (data_dir / "atp.sqlite3").write_bytes(b"SQLite format 3\x00-dummy-content")
    objects_dir = data_dir / "objects" / "screenshots" / "runs" / "1"
    objects_dir.mkdir(parents=True)
    (objects_dir / "step_0.png").write_bytes(b"\x89PNG-dummy-screenshot")

    _write_manifest(backup_dir)

    # 验证完整性校验通过
    _assert_manifest(backup_dir)


# ==================== 2. 坏备份与篡改防护 ====================


def test_backup_tampering_is_rejected(tmp_path):
    backup_dir = tmp_path / "backup-tampered"
    backup_dir.mkdir(parents=True, exist_ok=True)

    (backup_dir / "local-lite.env").write_text("APP_ENV=local\n", encoding="utf-8")
    _write_manifest(backup_dir)

    # 1. 篡改文件内容
    (backup_dir / "local-lite.env").write_text("APP_ENV=malicious\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Backup checksum mismatch"):
        _assert_manifest(backup_dir)


def test_backup_missing_file_is_rejected(tmp_path):
    backup_dir = tmp_path / "backup-missing"
    backup_dir.mkdir(parents=True, exist_ok=True)

    (backup_dir / "file1.txt").write_text("content1\n", encoding="utf-8")
    (backup_dir / "file2.txt").write_text("content2\n", encoding="utf-8")
    _write_manifest(backup_dir)

    # 删除其中一个文件
    (backup_dir / "file2.txt").unlink()
    with pytest.raises(RuntimeError, match="Backup file missing"):
        _assert_manifest(backup_dir)


def test_backup_unlisted_file_is_rejected(tmp_path):
    backup_dir = tmp_path / "backup-unlisted"
    backup_dir.mkdir(parents=True, exist_ok=True)

    (backup_dir / "file1.txt").write_text("content1\n", encoding="utf-8")
    _write_manifest(backup_dir)

    # 注入未经清单记录的文件
    (backup_dir / "injected_backdoor.txt").write_text("unlisted content\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Unlisted backup file"):
        _assert_manifest(backup_dir)


def test_backup_path_traversal_is_rejected(tmp_path):
    backup_dir = tmp_path / "backup-traversal"
    backup_dir.mkdir(parents=True, exist_ok=True)

    (backup_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format": 1,
                "files": [
                    {"path": "../../etc/passwd", "sha256": "abcdef"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="invalid path"):
        _assert_manifest(backup_dir)


# ==================== 3. 异目录完整恢复与数据可用性 ====================


def test_cross_directory_restore_and_database_reconnection(tmp_path):
    """测试将一个完整的备份包恢复至全新的独立目标目录，验证数据可正常读取并连接。"""
    source_backup_dir = tmp_path / "source-backup"
    source_backup_dir.mkdir(parents=True, exist_ok=True)

    # 创建源数据库并初始化真实 SQLite Schema
    src_db_file = source_backup_dir / "data" / "atp.sqlite3"
    src_db_file.parent.mkdir(parents=True, exist_ok=True)
    engine_src = create_engine(f"sqlite:///{src_db_file}")
    ensure_local_schema(engine_src)

    (source_backup_dir / "local-lite.env").write_text(
        "ATP_LOCAL_MODE=true\nAPP_ENV=local\nFIRST_ADMIN_USERNAME=admin\n", encoding="utf-8"
    )
    _write_manifest(source_backup_dir)

    # 目标目录（模拟全新机器或全新环境）
    target_restored_dir = tmp_path / "restored-target"
    target_restored_dir.mkdir(parents=True, exist_ok=True)

    # 执行恢复：先校验源清单
    _assert_manifest(source_backup_dir)

    # 拷贝并恢复数据
    import shutil

    for item in source_backup_dir.iterdir():
        if item.name == "manifest.json":
            continue
        dest = target_restored_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # 验证恢复后的数据
    restored_env = target_restored_dir / "local-lite.env"
    assert restored_env.exists()
    assert "FIRST_ADMIN_USERNAME=admin" in restored_env.read_text(encoding="utf-8")

    restored_db = target_restored_dir / "data" / "atp.sqlite3"
    assert restored_db.exists()

    # 连接恢复后的数据库，执行校验与版本检查
    engine_restored = create_engine(f"sqlite:///{restored_db}")
    version = ensure_local_schema(engine_restored)
    assert version == CURRENT_LOCAL_SCHEMA_VERSION

    with engine_restored.connect() as conn:
        inspector = inspect(conn)
        assert inspector is not None
        tables = inspector.get_table_names()
        assert "local_jobs" in tables
        assert "test_runs" in tables
