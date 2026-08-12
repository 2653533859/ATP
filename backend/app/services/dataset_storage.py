"""Shared validation for datasets stored directly in the database."""

from __future__ import annotations

import json

MAX_DATASET_ROWS = 500
MAX_DATASET_ROWS_BYTES = 256 * 1024


class DatasetStorageLimitError(ValueError):
    """Raised when database-backed dataset rows exceed the storage limits."""


def validate_dataset_rows_size(rows: list[dict]) -> None:
    if len(rows) > MAX_DATASET_ROWS:
        raise DatasetStorageLimitError(f"行数超过 {MAX_DATASET_ROWS} 上限；请拆分或改用 MinIO 引用模式")
    serialized = json.dumps(rows, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > MAX_DATASET_ROWS_BYTES:
        raise DatasetStorageLimitError(f"序列化后超过 {MAX_DATASET_ROWS_BYTES // 1024}KB；请精简或拆分")
