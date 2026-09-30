"""Signed local downloads reject invalid and missing paths."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import local_files


def test_local_file_rejects_wrong_mode_and_signature(monkeypatch):
    monkeypatch.setattr(local_files, "settings", SimpleNamespace(ATP_LOCAL_MODE=False))
    with pytest.raises(HTTPException) as exc:
        local_files.get_local_file("a.txt", 1, "signature")
    assert exc.value.status_code == 403

    monkeypatch.setattr(local_files, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    monkeypatch.setattr(local_files, "verify_signature", lambda *_args: False)
    with pytest.raises(HTTPException) as exc:
        local_files.get_local_file("a.txt", 1, "signature")
    assert exc.value.status_code == 403


def test_local_file_rejects_invalid_and_missing_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(local_files, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    monkeypatch.setattr(local_files, "verify_signature", lambda *_args: True)

    def invalid_path(_name):
        raise ValueError("outside root")

    monkeypatch.setattr(local_files, "object_path", invalid_path)
    with pytest.raises(HTTPException) as exc:
        local_files.get_local_file("../outside", 1, "signature")
    assert exc.value.status_code == 400

    monkeypatch.setattr(local_files, "object_path", lambda _name: tmp_path / "missing.txt")
    with pytest.raises(HTTPException) as exc:
        local_files.get_local_file("missing.txt", 1, "signature")
    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    ("content_type", "disposition"),
    [("image/png", "inline"), ("text/plain", "attachment")],
)
def test_local_file_returns_signed_object(monkeypatch, tmp_path, content_type, disposition):
    path = tmp_path / "example.txt"
    path.write_bytes(b"example")
    monkeypatch.setattr(local_files, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    monkeypatch.setattr(local_files, "verify_signature", lambda *_args: True)
    monkeypatch.setattr(local_files, "object_path", lambda _name: path)
    monkeypatch.setattr(local_files, "content_type_for", lambda _name: content_type)

    response = local_files.get_local_file("example.txt", 1, "signature")

    assert response.path == path
    assert response.media_type == content_type
    assert response.headers["content-disposition"].startswith(disposition)
