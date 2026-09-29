"""Filesystem object storage keeps paths inside its private root."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import local_object_store as storage


def test_local_object_roundtrip_and_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "settings", SimpleNamespace(LOCAL_DATA_PATH=tmp_path, APP_SECRET_KEY="test-key"))
    storage.upload_bytes("reports/one.html", b"<h1>one</h1>", "text/html")

    assert storage.read_bytes("reports/one.html") == b"<h1>one</h1>"
    assert storage.content_type_for("reports/one.html") == "text/html"
    assert [item.object_name for item in storage.list_objects("reports/")] == ["reports/one.html"]
    storage.delete_file("reports/one.html")
    assert storage.list_objects("reports/") == []
    assert storage.content_type_for("reports/one.html") == "text/html"


@pytest.mark.parametrize("object_name", ["../outside", "/absolute", "a/../../outside", "..\\outside"])
def test_local_object_rejects_traversal(tmp_path, monkeypatch, object_name: str) -> None:
    monkeypatch.setattr(storage, "settings", SimpleNamespace(LOCAL_DATA_PATH=tmp_path, APP_SECRET_KEY="test-key"))
    with pytest.raises(ValueError):
        storage.object_path(object_name)


def test_local_file_copy_and_signed_url(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "settings", SimpleNamespace(LOCAL_DATA_PATH=tmp_path, APP_SECRET_KEY="test-key"))
    source = tmp_path / "source.txt"
    source.write_bytes(b"local-copy")
    storage.upload_file("cases/request.txt", source, "text/plain")
    destination = tmp_path / "downloaded.txt"
    storage.download_file("cases/request.txt", destination)

    assert destination.read_bytes() == b"local-copy"
    assert storage.content_type_for("cases/request.txt") == "text/plain"
    signed = storage.signed_url("cases/request.txt", 60)
    from urllib.parse import parse_qs, urlparse

    query = parse_qs(urlparse(signed).query)
    expires = int(query["expires"][0])
    signature = query["signature"][0]
    assert storage.verify_signature("cases/request.txt", expires, signature)
    assert not storage.verify_signature("cases/other.txt", expires, signature)
    assert not storage.verify_signature("cases/request.txt", 0, signature)


def test_local_object_falls_back_to_mime_guess_for_bad_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "settings", SimpleNamespace(LOCAL_DATA_PATH=tmp_path, APP_SECRET_KEY="test-key"))
    storage.upload_bytes("images/capture.png", b"png", "image/png")
    storage._metadata_path("images/capture.png").write_text("invalid-json", encoding="utf-8")
    assert storage.content_type_for("images/capture.png") == "image/png"
    assert storage.list_objects("reports/") == []


def test_local_store_initializes_empty_directories_and_rejects_empty_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "settings", SimpleNamespace(LOCAL_DATA_PATH=tmp_path, APP_SECRET_KEY="test-key"))
    assert storage.list_objects() == []
    storage.ensure_store()
    assert (tmp_path / "objects").is_dir()
    assert (tmp_path / "object-metadata").is_dir()
    with pytest.raises(ValueError, match="invalid object name"):
        storage.object_path("")
