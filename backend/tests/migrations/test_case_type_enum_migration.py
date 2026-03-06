from pathlib import Path


def test_case_type_enum_migration_contains_new_values():
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    migration_files = sorted(versions_dir.glob("*.py"))

    assert migration_files, "缺少 Alembic 迁移文件，无法升级既有 PostgreSQL 枚举"

    merged_content = "\n".join(
        migration_file.read_text(encoding="utf-8") for migration_file in migration_files
    )

    assert "ALTER TYPE" in merged_content
    assert "graphql" in merged_content
    assert "websocket" in merged_content
    assert "grpc" in merged_content
