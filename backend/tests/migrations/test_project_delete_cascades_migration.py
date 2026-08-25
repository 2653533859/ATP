from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20260824_0065_fix_project_delete_cascades.py"


def test_project_owned_foreign_keys_use_cascade_and_environment_references_are_safe():
    content = MIGRATION.read_text(encoding="utf-8")

    for table_name in ("apks", "environments", "modules", "test_plans", "test_suites"):
        assert f'("{table_name}", "{table_name}_project_id_fkey", "CASCADE")' in content

    assert '"env_variables_env_id_fkey"' in content
    assert 'ondelete="CASCADE"' in content
    assert '"test_plans_env_id_fkey"' in content
    assert 'ondelete="SET NULL"' in content


def test_project_delete_migration_is_reversible_for_all_changed_constraints():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision: Union[str, None] = "20260824_0064"' in content
    assert "for table_name, constraint_name, _ondelete in reversed(_PROJECT_FOREIGN_KEYS)" in content
    assert 'op.drop_constraint("env_variables_env_id_fkey", "env_variables", type_="foreignkey")' in content
    assert 'op.drop_constraint("test_plans_env_id_fkey", "test_plans", type_="foreignkey")' in content
