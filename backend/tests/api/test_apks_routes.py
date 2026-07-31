"""apks API 路由单元测试（Q13 延伸覆盖：此前 38%，上传/下载链路少覆盖）。

伪造 MinIO 边界（ensure_bucket/upload_file/presigned_url/delete_file）与项目
访问检查，运行真实路由逻辑：分块暂存与 413 守卫、临时文件清理、非 .apk 400、
权限阶梯（上传/更新/删除 editor，查看/下载 viewer）、删除时 MinIO 异常吞掉、
预签名下载链接。FakeDB 承载对象与脚本化查询。
"""

import asyncio
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_a, **_kw):
    return None


_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_engineer", lambda: None),
    ("require_admin", lambda: None),
    ("assert_project_access", _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

_minio = sys.modules.setdefault("app.core.minio_client", types.SimpleNamespace())
for _name in ("ensure_bucket", "upload_file", "presigned_url", "delete_file"):
    if not hasattr(_minio, _name):
        setattr(_minio, _name, lambda *a, **kw: None)

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import apks as ak  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.models.user_project import ProjectRole  # noqa: E402
from app.schemas.apk import ApkUpdate  # noqa: E402


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, execute_results=None):
        self.objects = dict(objects or {})
        self.execute_results = list(execute_results or [])
        self.added = []
        self.deleted = []
        self.commits = 0

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = 800
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def execute(self, _query):
        return self.execute_results.pop(0) if self.execute_results else _FakeResult()

    async def refresh(self, obj):
        now = datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


class _FakeUpload:
    def __init__(self, filename, chunks):
        self.filename = filename
        self._chunks = list(chunks)
        self.closed = False

    async def read(self, _size=-1):
        return self._chunks.pop(0) if self._chunks else b""

    async def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    access_calls = []
    minio_calls = {"upload": [], "delete": [], "presigned": []}

    async def record_access(_db, _user, project_id, role):
        access_calls.append((project_id, role))

    def record_upload(object_name, path, content_type=None):
        # 记录调用时临时文件必须仍存在（finally 才清理）
        minio_calls["upload"].append((object_name, os.path.exists(path), content_type))

    monkeypatch.setattr(ak, "assert_project_access", record_access)
    monkeypatch.setattr(ak, "ensure_bucket", lambda: None)
    monkeypatch.setattr(ak, "upload_file", record_upload)
    monkeypatch.setattr(ak, "delete_file", lambda name: minio_calls["delete"].append(name))
    monkeypatch.setattr(
        ak,
        "presigned_url",
        lambda name, expires_seconds=0: minio_calls["presigned"].append((name, expires_seconds))
        or "https://minio/signed",
    )
    return {"access": access_calls, "minio": minio_calls}


def _user(uid=9):
    return _Obj(id=uid, username="amy")


def _apk(aid=1, project_id=5):
    return _Obj(
        id=aid,
        project_id=project_id,
        filename="app.apk",
        object_name=f"apks/projects/{project_id}/abcd1234_app.apk",
        file_size=10,
        package_name=None,
        version_name=None,
        version_code=None,
        description=None,
        uploaded_by=9,
    )


# ── 纯函数：对象名与分块暂存 ────────────────────────────────


def test_apk_object_name_format():
    name = ak._apk_object_name(5, "my app.apk")
    assert name.startswith("apks/projects/5/") and name.endswith("_my app.apk")
    short_id = name.split("/")[-1].split("_")[0]
    assert len(short_id) == 8


def test_save_upload_to_tempfile_chunks_and_size():
    upload = _FakeUpload("app.apk", [b"abc", b"de"])
    path, size = asyncio.run(ak._save_upload_to_tempfile(upload))
    try:
        assert size == 5
        with open(path, "rb") as fh:
            assert fh.read() == b"abcde"
    finally:
        os.remove(path)


def test_save_upload_to_tempfile_oversize_raises_413_and_cleans_temp(monkeypatch):
    created = {}
    real_ntf = ak.tempfile.NamedTemporaryFile

    def capture(*a, **kw):
        temp = real_ntf(*a, **kw)
        created["path"] = temp.name
        return temp

    monkeypatch.setattr(ak.tempfile, "NamedTemporaryFile", capture)

    upload = _FakeUpload("big.apk", [b"x" * 10])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ak._save_upload_to_tempfile(upload, max_size=5))

    assert exc.value.status_code == 413
    assert not os.path.exists(created["path"])  # 异常路径也清理临时文件


# ── upload：校验阶梯 + MinIO 边界 + 清理 ────────────────────


def test_upload_apk_project_not_found(stubs):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ak.upload_apk(
                project_id=5,
                file=_FakeUpload("app.apk", [b"x"]),
                package_name=None,
                version_name=None,
                version_code=None,
                description=None,
                db=_FakeDB(),
                current_user=_user(),
            )
        )
    assert exc.value.status_code == 404
    assert stubs["access"] == [(5, ProjectRole.editor)]


def test_upload_apk_rejects_non_apk_extension():
    db = _FakeDB({("Project", 5): _Obj(id=5)})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ak.upload_apk(
                project_id=5,
                file=_FakeUpload("app.ipa", [b"x"]),
                package_name=None,
                version_name=None,
                version_code=None,
                description=None,
                db=db,
                current_user=_user(),
            )
        )
    assert exc.value.status_code == 400


def test_upload_apk_happy_path_uploads_and_creates_row(stubs):
    db = _FakeDB({("Project", 5): _Obj(id=5)})
    upload = _FakeUpload("app.apk", [b"abc", b"defg"])

    apk = asyncio.run(
        ak.upload_apk(
            project_id=5,
            file=upload,
            package_name="com.demo",
            version_name="1.2.0",
            version_code=120,
            description="演示包",
            db=db,
            current_user=_user(uid=9),
        )
    )

    object_name, temp_existed_at_upload, content_type = stubs["minio"]["upload"][0]
    assert object_name.startswith("apks/projects/5/") and object_name.endswith("_app.apk")
    assert temp_existed_at_upload  # 上传时临时文件在，finally 后清理
    assert content_type == "application/vnd.android.package-archive"
    assert upload.closed
    assert apk.file_size == 7 and apk.uploaded_by == 9 and apk.package_name == "com.demo"
    assert db.added == [apk] and db.commits == 1


# ── list / get / update / delete / download ─────────────────


def test_list_apks_filters_by_project_with_viewer_access(stubs):
    db = _FakeDB(execute_results=[_FakeResult(rows=[_apk()])])
    out = asyncio.run(ak.list_apks(project_id=5, db=db, user=_user()))
    assert [a.id for a in out] == [1]
    assert stubs["access"] == [(5, ProjectRole.viewer)]


def test_list_apks_without_project_skips_access_check(stubs):
    db = _FakeDB(execute_results=[_FakeResult(rows=[])])
    assert asyncio.run(ak.list_apks(project_id=None, db=db, user=_user())) == []
    assert stubs["access"] == []


def test_get_apk_404_and_happy(stubs):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ak.get_apk(apk_id=404, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404

    db = _FakeDB({("Apk", 1): _apk()})
    out = asyncio.run(ak.get_apk(apk_id=1, db=db, user=_user()))
    assert out.id == 1 and stubs["access"] == [(5, ProjectRole.viewer)]


def test_update_apk_patches_only_provided_fields(stubs):
    apk = _apk()
    db = _FakeDB({("Apk", 1): apk})

    asyncio.run(ak.update_apk(apk_id=1, body=ApkUpdate(description="新描述"), db=db, user=_user()))

    assert apk.description == "新描述"
    assert apk.package_name is None  # exclude_none：未提供字段不动
    assert stubs["access"] == [(5, ProjectRole.editor)]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ak.update_apk(apk_id=404, body=ApkUpdate(), db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_delete_apk_swallows_minio_failure_and_removes_row(stubs, monkeypatch):
    apk = _apk()
    db = _FakeDB({("Apk", 1): apk})

    def broken_delete(_name):
        raise RuntimeError("minio down")

    monkeypatch.setattr(ak, "delete_file", broken_delete)

    asyncio.run(ak.delete_apk(apk_id=1, db=db, user=_user()))

    assert db.deleted == [apk] and db.commits == 1  # MinIO 失败不阻断删除

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ak.delete_apk(apk_id=404, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_download_apk_returns_presigned_url(stubs):
    db = _FakeDB({("Apk", 1): _apk()})

    out = asyncio.run(ak.download_apk(apk_id=1, db=db, user=_user()))

    assert out == {"url": "https://minio/signed", "filename": "app.apk"}
    assert stubs["minio"]["presigned"] == [("apks/projects/5/abcd1234_app.apk", 3600)]
    assert stubs["access"] == [(5, ProjectRole.viewer)]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ak.download_apk(apk_id=404, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404
