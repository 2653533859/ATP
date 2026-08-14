from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "20260814_0059_add_mobile_run_events.py"


def test_mobile_run_events_migration_is_latest_and_has_ordered_event_index():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0059"' in content
    assert 'down_revision: Union[str, None] = "20260814_0058"' in content
    assert '"mobile_run_events"' in content
    assert '"ix_mobile_run_events_run_sequence"' in content


def test_mobile_run_events_migration_drops_only_its_own_table():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'op.drop_table("mobile_run_events")' in content
    assert "artifact_type" not in content
