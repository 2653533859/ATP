import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260525_0029_add_test_runs_case_id_status_created_at_index.py"
    )


def test_q5_compound_index_migration_upgrade_creates_index():
    content = _migration_path().read_text(encoding="utf-8")
    assert (
        'op.create_index(\n        "ix_test_runs_case_id_status_created_at",\n'
        '        "test_runs",\n        ["case_id", "status", "created_at"],\n    )'
    ) in content


def test_q5_compound_index_migration_downgrade_drops_index():
    content = _migration_path().read_text(encoding="utf-8")
    assert (
        'op.drop_index("ix_test_runs_case_id_status_created_at", table_name="test_runs")'
        in content
    )


def test_q5_compound_index_migration_chain_position():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'revision: str = "20260525_0029"' in content
    assert 'down_revision: Union[str, None] = "20260522_0028"' in content
