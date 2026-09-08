"""Regression coverage for the execution command ledger migration."""

from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260908_0069_add_execution_commands.py"


def test_execution_command_migration_extends_current_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260908_0069"' in content
    assert 'down_revision: Union[str, None] = "20260901_0068"' in content


def test_execution_command_migration_has_idempotency_and_audit_fields():
    content = MIGRATION.read_text(encoding="utf-8")

    assert '"execution_commands"' in content
    assert '"uq_execution_commands_user_command"' in content
    assert '"uq_execution_commands_target_action"' in content
    assert "status IN ('processing', 'succeeded', 'indeterminate')" in content
    assert '"response_json"' in content
    assert '"source_status"' in content
    assert '"result_status"' in content
    assert '"error_status_code"' in content


def test_execution_command_migration_is_reversible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'op.drop_table("execution_commands")' in content
