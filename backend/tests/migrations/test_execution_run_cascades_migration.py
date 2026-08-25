from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20260825_0066_fix_execution_run_cascades.py"


def test_execution_history_foreign_keys_cascade_or_null_on_owner_deletion():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision: Union[str, None] = "20260824_0065"' in content
    for table_name, constraint_name, _referred_table, _referred_column, ondelete in (
        ("modules", "modules_parent_id_fkey", "modules", "id", "CASCADE"),
        ("test_cases", "test_cases_module_id_fkey", "modules", "id", "CASCADE"),
        ("test_cases", "test_cases_dataset_id_fkey", "test_datasets", "id", "SET NULL"),
        ("test_runs", "test_runs_case_id_fkey", "test_cases", "id", "CASCADE"),
        ("test_runs", "test_runs_parent_run_id_fkey", "test_runs", "id", "CASCADE"),
        ("step_results", "step_results_run_id_fkey", "test_runs", "id", "CASCADE"),
        ("suite_runs", "suite_runs_suite_id_fkey", "test_suites", "id", "CASCADE"),
        ("plan_runs", "plan_runs_plan_id_fkey", "test_plans", "id", "CASCADE"),
    ):
        assert f'("{table_name}", "{constraint_name}"' in content
        assert f'"{ondelete}"' in content


def test_execution_history_migration_recreates_constraints_in_downgrade():
    content = MIGRATION.read_text(encoding="utf-8")

    assert (
        "for table_name, constraint_name, referred_table, referred_column, _ondelete in reversed(_FOREIGN_KEYS)"
        in content
    )
    assert 'op.drop_constraint(constraint_name, table_name, type_="foreignkey")' in content
    assert "op.create_foreign_key(" in content
