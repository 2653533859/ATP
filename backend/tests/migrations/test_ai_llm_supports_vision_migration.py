from pathlib import Path


def _migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260528_0033_add_ai_llm_supports_vision.py"
    )


def test_ai_llm_supports_vision_migration_chain_position():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'revision: str = "20260528_0033"' in content
    assert 'down_revision: Union[str, None] = "20260528_0032"' in content


def test_ai_llm_supports_vision_migration_adds_boolean_default_false():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'op.add_column(\n        "ai_llm_configs",' in content
    assert '"supports_vision"' in content
    assert "server_default=sa.false()" in content


def test_ai_llm_supports_vision_migration_downgrade_drops_column():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'op.drop_column("ai_llm_configs", "supports_vision")' in content
