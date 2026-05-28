from pathlib import Path


def _migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260528_0031_add_healing_feedback_aggregates.py"
    )


def test_healing_feedback_aggregates_migration_chain_position():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'revision: str = "20260528_0031"' in content
    assert 'down_revision: Union[str, None] = "20260527_0030"' in content


def test_healing_feedback_aggregates_migration_creates_table_and_indexes():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'op.create_table(\n        "healing_feedback_aggregates",' in content
    assert '"uq_healing_feedback_aggregate_fingerprint_case_type"' in content
    assert '"ix_healing_feedback_aggregates_case_rate"' in content


def test_healing_feedback_aggregates_migration_downgrade_drops_table():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'op.drop_index("ix_healing_feedback_aggregates_case_rate"' in content
    assert 'op.drop_table("healing_feedback_aggregates")' in content
