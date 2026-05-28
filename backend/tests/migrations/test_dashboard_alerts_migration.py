import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260527_0030_add_dashboard_alerts.py"
    )


def test_dashboard_alerts_migration_chain_position():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'revision: str = "20260527_0030"' in content
    assert 'down_revision: Union[str, None] = "20260525_0029"' in content


def test_dashboard_alerts_migration_creates_rules_and_events_tables():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'op.create_table(\n        "dashboard_alert_rules",' in content
    assert 'op.create_table(\n        "dashboard_alert_events",' in content
    assert '"ix_dashboard_alert_rules_project_enabled"' in content
    assert '"ix_dashboard_alert_events_rule_triggered"' in content


def test_dashboard_alerts_migration_downgrade_drops_tables_and_enums():
    content = _migration_path().read_text(encoding="utf-8")
    assert 'op.drop_table("dashboard_alert_events")' in content
    assert 'op.drop_table("dashboard_alert_rules")' in content
    assert "operator_enum.drop(op.get_bind(), checkfirst=True)" in content
    assert "metric_enum.drop(op.get_bind(), checkfirst=True)" in content
