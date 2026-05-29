import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.dataset_schema import DatasetSchemaField, validate_dataset_rows


def test_validate_dataset_rows_accepts_matching_rows():
    result = validate_dataset_rows(
        rows=[{"name": "alice", "age": 18, "active": True}],
        schema=[
            DatasetSchemaField(name="name", type="string", required=True),
            DatasetSchemaField(name="age", type="integer", required=True),
            DatasetSchemaField(name="active", type="boolean"),
        ],
    )

    assert result.valid is True
    assert result.issues == []
    assert result.normalized_rows == [{"name": "alice", "age": 18, "active": True}]


def test_validate_dataset_rows_reports_missing_and_type_errors():
    result = validate_dataset_rows(
        rows=[{"name": 42}, {"age": "18"}],
        schema=[
            DatasetSchemaField(name="name", type="string", required=True),
            DatasetSchemaField(name="age", type="integer", required=True),
        ],
    )

    assert result.valid is False
    assert [(i.row_index, i.field) for i in result.issues] == [
        (0, "name"),
        (0, "age"),
        (1, "name"),
        (1, "age"),
    ]


def test_validate_dataset_rows_applies_defaults_to_preview():
    result = validate_dataset_rows(
        rows=[{"name": "alice"}],
        schema=[DatasetSchemaField(name="role", type="string", default="tester")],
    )

    assert result.valid is True
    assert result.normalized_rows == [{"name": "alice", "role": "tester"}]


def test_validate_dataset_rows_respects_preview_limit():
    result = validate_dataset_rows(
        rows=[{"i": 1}, {"i": 2}, {"i": 3}],
        schema=[],
        preview_limit=2,
    )

    assert result.row_count == 3
    assert result.normalized_rows == [{"i": 1}, {"i": 2}]
