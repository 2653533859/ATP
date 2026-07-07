from __future__ import annotations

from pathlib import Path


def test_suite_config_column_is_covered_by_migration():
    content = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260529_0039_add_suite_config.py"
    ).read_text(encoding="utf-8")

    assert 'op.add_column(\n        "test_suites",' in content
    assert '"config"' in content
    assert "sa.JSON()" in content
    assert 'op.drop_column("test_suites", "config")' in content
