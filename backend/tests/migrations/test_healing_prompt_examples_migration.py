from pathlib import Path


def _migration_path() -> Path:
    return Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260528_0032_add_healing_prompt_examples.py"


def test_healing_prompt_examples_migration_chain_position():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'revision: str = "20260528_0032"' in content
    assert 'down_revision: Union[str, None] = "20260528_0031"' in content


def test_healing_prompt_examples_migration_creates_table_and_indexes():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'op.create_table(\n        "healing_prompt_examples",' in content
    assert '"ix_healing_prompt_examples_quality_lookup"' in content
    assert 'sa.ForeignKeyConstraint(["source_step_result_id"], ["step_results.id"], ondelete="SET NULL")' in content


def test_healing_prompt_examples_migration_downgrade_drops_table():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'op.drop_index("ix_healing_prompt_examples_quality_lookup"' in content
    assert 'op.drop_table("healing_prompt_examples")' in content
