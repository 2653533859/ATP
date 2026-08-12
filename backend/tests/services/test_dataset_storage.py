"""Tests for database and MinIO-backed dataset storage boundaries."""

from types import SimpleNamespace

import pytest

from app.services import dataset_storage


def test_database_mode_keeps_the_existing_small_dataset_limit():
    with pytest.raises(dataset_storage.DatasetStorageLimitError, match="500"):
        dataset_storage.validate_dataset_rows_size([{"id": index} for index in range(501)])


def test_minio_mode_allows_more_rows_but_has_an_object_size_limit():
    dataset_storage.validate_dataset_rows_size([{"id": index} for index in range(501)], "minio")
    with pytest.raises(dataset_storage.DatasetStorageLimitError, match="50MB"):
        dataset_storage.validate_dataset_rows_size([{"value": "x" * (51 * 1024 * 1024)}], "minio")


def test_upload_and_read_minio_rows_use_a_stable_object_reference(monkeypatch):
    calls: list[tuple[str, bytes, str]] = []

    def fake_upload(object_name, data, content_type):
        calls.append((object_name, data, content_type))

    monkeypatch.setattr(dataset_storage.minio_client, "upload_bytes", fake_upload)
    monkeypatch.setattr(
        dataset_storage.minio_client,
        "read_bytes",
        lambda object_name: next(data for name, data, _content_type in calls if name == object_name),
    )

    object_name = dataset_storage.upload_dataset_rows(project_id=3, dataset_id=7, rows=[{"name": "alice"}], version=2)

    assert object_name == "datasets/3/7/version-2.json"
    assert calls[0][2] == "application/json"
    assert dataset_storage.read_dataset_rows(object_name) == [{"name": "alice"}]


def test_rows_from_source_reads_minio_references(monkeypatch):
    monkeypatch.setattr(dataset_storage, "read_dataset_rows", lambda object_name: [{"object": object_name}])

    source = SimpleNamespace(storage_mode="minio", object_name="datasets/1/2/current.json", rows=[])

    assert dataset_storage.rows_from_source(source) == [{"object": "datasets/1/2/current.json"}]


def test_delete_dataset_objects_removes_current_and_version_objects(monkeypatch):
    deleted: list[str] = []
    monkeypatch.setattr(
        dataset_storage.minio_client,
        "list_objects",
        lambda prefix: [
            SimpleNamespace(object_name=f"{prefix}current.json"),
            SimpleNamespace(object_name=f"{prefix}version-1.json"),
        ],
    )
    monkeypatch.setattr(dataset_storage.minio_client, "delete_file", deleted.append)

    assert dataset_storage.delete_dataset_objects(3, 7) == 2
    assert deleted == ["datasets/3/7/current.json", "datasets/3/7/version-1.json"]


def test_reconcile_dataset_objects_is_a_dry_run_by_default(monkeypatch):
    prefix = "datasets/3/"
    monkeypatch.setattr(
        dataset_storage.minio_client,
        "list_objects",
        lambda prefix: [
            SimpleNamespace(object_name=f"{prefix}7/current.json"),
            SimpleNamespace(object_name=f"{prefix}7/version-1.json"),
            SimpleNamespace(object_name=f"{prefix}8/current.json"),
            SimpleNamespace(object_name="other/ignore.json"),
        ],
    )
    deleted: list[str] = []
    monkeypatch.setattr(dataset_storage.minio_client, "delete_file", deleted.append)

    result = dataset_storage.reconcile_dataset_objects(
        3,
        {f"{prefix}7/current.json", f"{prefix}7/version-1.json", "other/protected.json"},
    )

    assert result["dry_run"] is True
    assert result["scanned_count"] == 3
    assert result["referenced_count"] == 2
    assert result["orphaned_objects"] == [f"{prefix}8/current.json"]
    assert result["deleted_count"] == 0
    assert deleted == []


def test_reconcile_dataset_objects_purge_reports_partial_delete_failures(monkeypatch):
    prefix = "datasets/3/"
    monkeypatch.setattr(
        dataset_storage.minio_client,
        "list_objects",
        lambda prefix: [
            SimpleNamespace(object_name=f"{prefix}7/current.json"),
            SimpleNamespace(object_name=f"{prefix}8/current.json"),
        ],
    )
    deleted: list[str] = []

    def delete(object_name: str):
        if object_name.endswith("8/current.json"):
            raise RuntimeError("permission denied")
        deleted.append(object_name)

    monkeypatch.setattr(dataset_storage.minio_client, "delete_file", delete)

    result = dataset_storage.reconcile_dataset_objects(
        3,
        {f"{prefix}7/current.json"},
        purge=True,
    )

    assert result["dry_run"] is False
    assert result["orphan_count"] == 1
    assert result["deleted_count"] == 0
    assert result["errors"] == [f"{prefix}8/current.json: permission denied"]
    assert deleted == []


def test_cleanup_dataset_object_names_is_scoped_and_reports_delete_errors(monkeypatch):
    deleted: list[str] = []

    def delete(object_name: str):
        if object_name.endswith("version-2.json"):
            raise RuntimeError("temporarily unavailable")
        deleted.append(object_name)

    monkeypatch.setattr(dataset_storage.minio_client, "delete_file", delete)

    errors = dataset_storage.cleanup_dataset_object_names(
        3,
        7,
        [
            "datasets/3/7/current-new.json",
            "datasets/3/7/version-2.json",
            "datasets/9/7/unsafe.json",
        ],
    )

    assert deleted == ["datasets/3/7/current-new.json"]
    assert errors == [
        "datasets/3/7/version-2.json: temporarily unavailable",
        "datasets/9/7/unsafe.json: object is outside dataset prefix",
    ]
