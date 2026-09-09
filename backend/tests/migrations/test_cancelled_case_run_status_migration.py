from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20260909_0072_add_cancelled_case_run_status.py"


def test_cancelled_case_run_status_migration_is_chained_and_downgrade_compatible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision: Union[str, None] = "20260909_0071"' in content
    assert "ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'cancelled'" in content
    assert "UPDATE test_runs SET status = 'failed' WHERE status = 'cancelled'" in content
