from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20260909_0071_fix_web_asset_timestamp_defaults.py"


def test_web_asset_timestamp_defaults_migration_covers_all_asset_tables():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision: Union[str, None] = "20260908_0070"' in content
    for table_name in ("web_element_assets", "web_page_objects", "web_visual_baselines"):
        assert f'"{table_name}"' in content
    assert content.count("server_default=sa.func.now()") == 2
    assert content.count("server_default=None") == 2
