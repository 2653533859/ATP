from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20261126_0093_fix_asset_timestamp_defaults.py"


def test_asset_timestamp_defaults_migration_covers_schema_and_contract_assets():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision: Union[str, None] = "20261117_0092"' in content
    for table_name in ("api_schema_assets", "api_contract_assets"):
        assert f'"{table_name}"' in content
    assert content.count("server_default=sa.func.now()") == 2
    assert content.count("server_default=None") == 2
