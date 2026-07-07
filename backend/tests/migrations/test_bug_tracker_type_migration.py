from __future__ import annotations

from pathlib import Path


def test_bug_tracker_type_enum_conversion_is_covered_by_migration():
    content = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260529_0040_convert_bug_tracker_type_enum.py"
    ).read_text(encoding="utf-8")

    assert 'name="trackertype"' in content
    assert "tracker_type_enum.create(bind, checkfirst=True)" in content
    assert 'op.alter_column(\n            "bug_trackers",' in content
    assert 'postgresql_using="tracker_type::trackertype"' in content
    assert 'postgresql_using="tracker_type::text"' in content
