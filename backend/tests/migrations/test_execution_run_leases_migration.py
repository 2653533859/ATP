"""Regression coverage for the execution run lease migration."""

from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260908_0070_add_execution_run_leases.py"


def test_execution_run_lease_migration_extends_command_ledger_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260908_0070"' in content
    assert 'down_revision: Union[str, None] = "20260908_0069"' in content


def test_execution_run_lease_migration_has_ownership_and_expiry_fields():
    content = MIGRATION.read_text(encoding="utf-8")

    assert '"execution_run_leases"' in content
    assert '"uq_execution_run_leases_target"' in content
    assert '"ix_execution_run_leases_status_expires"' in content
    for field in ("lease_token", "worker_id", "celery_task_id", "heartbeat_at", "expires_at", "failure_reason"):
        assert f'"{field}"' in content


def test_execution_run_lease_migration_is_reversible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'op.drop_table("execution_run_leases")' in content
