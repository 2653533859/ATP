from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


DatasetFieldType = Literal["string", "number", "integer", "boolean", "object", "array"]


@dataclass(frozen=True)
class DatasetSchemaField:
    name: str
    type: DatasetFieldType = "string"
    required: bool = False
    default: Any = None


@dataclass
class DatasetValidationIssue:
    row_index: int
    field: str
    message: str


@dataclass
class DatasetValidationResult:
    valid: bool
    row_count: int
    normalized_rows: list[dict[str, Any]]
    issues: list[DatasetValidationIssue] = field(default_factory=list)


def _matches_type(value: Any, field_type: DatasetFieldType) -> bool:
    if field_type == "string":
        return isinstance(value, str)
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == "boolean":
        return isinstance(value, bool)
    if field_type == "object":
        return isinstance(value, dict)
    if field_type == "array":
        return isinstance(value, list)
    return False


def validate_dataset_rows(
    rows: list[dict[str, Any]],
    schema: list[DatasetSchemaField],
    *,
    preview_limit: int = 5,
) -> DatasetValidationResult:
    issues: list[DatasetValidationIssue] = []
    normalized_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        normalized = dict(row)
        for field in schema:
            exists = field.name in normalized and normalized[field.name] is not None
            if not exists and field.default is not None:
                normalized[field.name] = field.default
                exists = True
            if field.required and not exists:
                issues.append(DatasetValidationIssue(idx, field.name, "required field is missing"))
                continue
            if exists and not _matches_type(normalized[field.name], field.type):
                issues.append(
                    DatasetValidationIssue(
                        idx,
                        field.name,
                        f"expected {field.type}, got {type(normalized[field.name]).__name__}",
                    )
                )
        if len(normalized_rows) < preview_limit:
            normalized_rows.append(normalized)

    return DatasetValidationResult(
        valid=not issues,
        row_count=len(rows),
        normalized_rows=normalized_rows,
        issues=issues,
    )
