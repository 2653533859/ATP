"""补齐 ios.py 的未覆盖分支：IPA 上传、设备 CRUD/心跳、租约端点与 App 资产管理。"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import ios
from app.models.bootstrap import load_all_models
from app.models.ios import IosDeviceStatus
from app.schemas.device_lease import DeviceLeaseAcquireIn, DeviceLeaseTokenIn
from app.schemas.ios import IosAppUpdate, IosDeviceCreate, IosDeviceUpdate
from app.services.ios_device_leases import IosDeviceLeaseConflict

load_all_models()

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
TOKEN = "lease-token-0123456789abcdef"


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows if rows is not None else []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """极简异步会话：get/execute 走预置映射，写操作只记录调用。"""

    def __init__(self, objects=None, results=None):
        self.objects = dict(objects or {})
        self.results = list(results or [])
        self.added = []
        self.deleted = []
        self.commits = 0

    async def get(self, model, ident):
        value = self.objects.get(model)
        return value(ident) if callable(value) else value

    async def execute(self, _statement):
        if self.results:
            return self.results.pop(0)
        return _Result()

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        return value

    async def flush(self):
        return None


class _Upload:
    """最小 UploadFile 替身：按序吐出分片，耗尽后返回空字节串。"""

    def __init__(self, chunks, filename="demo.ipa"):
        self._chunks = list(chunks)
        self.filename = filename
        self.closed = False

    async def read(self, _size):
        if not self._chunks:
            return b""
        value = self._chunks.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def close(self):
        self.closed = True


def _user(user_id: int = 7):
    return SimpleNamespace(id=user_id, username="engineer", role="engineer")


def _device(device_id: int = 3, *, status: IosDeviceStatus = IosDeviceStatus.online):
    return SimpleNamespace(
        id=device_id,
        udid="00008110-000A1B2C3D4E",
        name="iPhone 15",
        model="iPhone15,2",
        platform_version="17.4",
        status=status,
        appium_server_url="http://127.0.0.1:4723",
        wda_local_port=None,
        ip_address=None,
        port=None,
        description=None,
        last_seen_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _app_row(app_id: int = 41, project_id: int = 1):
    return SimpleNamespace(
        id=app_id,
        project_id=project_id,
        filename="Demo.ipa",
        bundle_id="com.demo.app",
        version_name="1.0.0",
        file_size=1024,
        object_name="ios-apps/projects/1/abcd1234_Demo.ipa",
        signing_identity=None,
        provisioning_profile=None,
        description=None,
        uploaded_by=7,
        created_at=NOW,
        updated_at=NOW,
    )


def _lease(device_id: int = 3):
    return SimpleNamespace(
        device_id=device_id,
        owner_id=7,
        owner_label="manual",
        acquired_at=NOW,
        heartbeat_at=NOW,
        expires_at=NOW + timedelta(seconds=900),
        lease_token=TOKEN,
    )


def _no_access(monkeypatch):
    calls = []

    async def fake_access(_db, _user_obj, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(ios, "assert_project_access", fake_access)
    return calls


def _record(monkeypatch, name, value=None):
    """替换模块内同步函数（minio/presigned 等）并记录调用。"""

    calls = []

    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return value

    monkeypatch.setattr(ios, name, fake)
    return calls


def _track_tempfile(monkeypatch):
    created = []
    real = tempfile.NamedTemporaryFile

    def tracking(*args, **kwargs):
        handle = real(*args, **kwargs)
        created.append(handle.name)
        return handle

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", tracking)
    return created


def test_safe_save_upload_streams_chunks_and_returns_path():
    path, total = asyncio.run(ios._save_upload(_Upload([b"abc", b"de"])))
    try:
        assert total == 5
        with open(path, "rb") as handle:
            assert handle.read() == b"abcde"
    finally:
        os.remove(path)


def test_save_upload_rejects_oversize_and_cleans_temp(monkeypatch):
    created = _track_tempfile(monkeypatch)
    monkeypatch.setattr(ios, "_MAX_IPA_SIZE", 4)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ios._save_upload(_Upload([b"12345"])))
    assert exc.value.status_code == 413
    assert created and not os.path.exists(created[0])


def test_save_upload_propagates_read_error_and_cleans_temp(monkeypatch):
    created = _track_tempfile(monkeypatch)
    with pytest.raises(RuntimeError):
        asyncio.run(ios._save_upload(_Upload([RuntimeError("disk failure")])))
    assert created and not os.path.exists(created[0])


def test_list_ios_devices_status_filter():
    rows = [_device()]
    db = _FakeDB(results=[_Result(rows=rows)])
    result = asyncio.run(ios.list_ios_devices(status_filter=IosDeviceStatus.online, db=db, _user=_user()))
    assert result == rows

    unfiltered = asyncio.run(
        ios.list_ios_devices(status_filter=None, db=_FakeDB(results=[_Result(rows=rows)]), _user=_user())
    )
    assert unfiltered == rows


def test_create_ios_device_conflict_and_success():
    existing = _device()
    with pytest.raises(HTTPException) as conflict:
        asyncio.run(
            ios.create_ios_device(
                body=IosDeviceCreate(udid=existing.udid),
                db=_FakeDB(results=[_Result(scalar=existing)]),
                _user=_user(),
            )
        )
    assert conflict.value.status_code == 409

    db = _FakeDB(results=[_Result()])
    device = asyncio.run(ios.create_ios_device(body=IosDeviceCreate(udid="00008110-FFFF"), db=db, _user=_user()))
    assert isinstance(device, ios.IosDevice)
    assert device.appium_server_url == "http://127.0.0.1:4723/"
    assert db.added == [device]
    assert db.commits == 1


def test_update_ios_device_404_and_url_conversion():
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ios.update_ios_device(device_id=3, body=IosDeviceUpdate(name="x"), db=_FakeDB(), _user=_user()))
    assert missing.value.status_code == 404

    device = _device()
    db = _FakeDB(objects={ios.IosDevice: device})
    body = IosDeviceUpdate(name="改后名称", appium_server_url="http://10.0.0.9:4723")
    result = asyncio.run(ios.update_ios_device(device_id=3, body=body, db=db, _user=_user()))
    assert result is device
    assert device.name == "改后名称"
    assert device.appium_server_url == "http://10.0.0.9:4723/"
    assert db.commits == 1

    plain = _device()
    plain_db = _FakeDB(objects={ios.IosDevice: plain})
    result = asyncio.run(
        ios.update_ios_device(device_id=3, body=IosDeviceUpdate(name="仅改名称"), db=plain_db, _user=_user())
    )
    assert result is plain
    assert plain.appium_server_url == "http://127.0.0.1:4723"


def test_delete_ios_device_404_and_success():
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ios.delete_ios_device(device_id=3, db=_FakeDB(), _user=_user()))
    assert missing.value.status_code == 404

    device = _device()
    db = _FakeDB(objects={ios.IosDevice: device})
    assert asyncio.run(ios.delete_ios_device(device_id=3, db=db, _user=_user())) is None
    assert db.deleted == [device]
    assert db.commits == 1


def test_heartbeat_ios_device_transitions_status():
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ios.heartbeat_ios_device_endpoint(device_id=3, db=_FakeDB(), _user=_user()))
    assert missing.value.status_code == 404

    busy = _device(status=IosDeviceStatus.busy)
    asyncio.run(
        ios.heartbeat_ios_device_endpoint(device_id=3, db=_FakeDB(objects={ios.IosDevice: busy}), _user=_user())
    )
    assert busy.status == IosDeviceStatus.busy
    assert busy.last_seen_at is not None

    idle = _device(status=IosDeviceStatus.offline)
    asyncio.run(
        ios.heartbeat_ios_device_endpoint(device_id=3, db=_FakeDB(objects={ios.IosDevice: idle}), _user=_user())
    )
    assert idle.status == IosDeviceStatus.online


def test_acquire_ios_lease_conflict_and_lookup_error(monkeypatch):
    async def conflict(*_args, **_kwargs):
        raise IosDeviceLeaseConflict("iOS 设备已被其他任务占用")

    monkeypatch.setattr(ios, "acquire_ios_device_lease", conflict)
    with pytest.raises(HTTPException) as busy:
        asyncio.run(ios.acquire_ios_lease(device_id=3, body=DeviceLeaseAcquireIn(), db=_FakeDB(), current_user=_user()))
    assert busy.value.status_code == 409
    assert "占用" in busy.value.detail

    async def missing(*_args, **_kwargs):
        raise LookupError("iOS 设备不存在")

    monkeypatch.setattr(ios, "acquire_ios_device_lease", missing)
    with pytest.raises(HTTPException) as gone:
        asyncio.run(ios.acquire_ios_lease(device_id=3, body=DeviceLeaseAcquireIn(), db=_FakeDB(), current_user=_user()))
    assert gone.value.status_code == 409


def test_acquire_ios_lease_success(monkeypatch):
    lease = _lease()
    calls = []

    async def fake_acquire(_db, device_id, *, owner_id, owner_label, ttl_seconds):
        calls.append((device_id, owner_id, owner_label, ttl_seconds))
        return lease

    monkeypatch.setattr(ios, "acquire_ios_device_lease", fake_acquire)
    db = _FakeDB()
    result = asyncio.run(
        ios.acquire_ios_lease(device_id=3, body=DeviceLeaseAcquireIn(owner_label="suite"), db=db, current_user=_user())
    )
    assert result is lease
    assert calls == [(3, 7, "suite", 900)]
    assert db.commits == 1


def test_heartbeat_ios_lease_strips_token_and_conflict(monkeypatch):
    lease = _lease()

    async def fake_heartbeat(_db, device_id, token):
        assert token == TOKEN
        return lease

    monkeypatch.setattr(ios, "heartbeat_ios_device_lease", fake_heartbeat)
    db = _FakeDB()
    result = asyncio.run(
        ios.heartbeat_ios_lease(device_id=3, body=DeviceLeaseTokenIn(lease_token=TOKEN), db=db, _user=_user())
    )
    assert result.lease_token is None
    assert result.device_id == 3
    assert db.commits == 1

    async def conflict(*_args, **_kwargs):
        raise IosDeviceLeaseConflict("iOS 设备租约不存在或已过期")

    monkeypatch.setattr(ios, "heartbeat_ios_device_lease", conflict)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ios.heartbeat_ios_lease(
                device_id=3, body=DeviceLeaseTokenIn(lease_token=TOKEN), db=_FakeDB(), _user=_user()
            )
        )
    assert exc.value.status_code == 409


def test_release_ios_lease_success_and_missing(monkeypatch):
    calls = []

    async def released(_db, device_id, token):
        calls.append((device_id, token))
        return True

    monkeypatch.setattr(ios, "release_ios_device_lease", released)
    db = _FakeDB()
    assert (
        asyncio.run(
            ios.release_ios_lease(device_id=3, body=DeviceLeaseTokenIn(lease_token=TOKEN), db=db, _user=_user())
        )
        is None
    )
    assert calls == [(3, TOKEN)]
    assert db.commits == 1

    async def missing(*_args, **_kwargs):
        return False

    monkeypatch.setattr(ios, "release_ios_device_lease", missing)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ios.release_ios_lease(device_id=3, body=DeviceLeaseTokenIn(lease_token=TOKEN), db=_FakeDB(), _user=_user())
        )
    assert exc.value.status_code == 404


def test_upload_ios_app_404_and_bad_extension(monkeypatch):
    _no_access(monkeypatch)
    with pytest.raises(HTTPException) as missing:
        asyncio.run(
            ios.upload_ios_app(project_id=1, file=_Upload([], filename="a.ipa"), db=_FakeDB(), current_user=_user())
        )
    assert missing.value.status_code == 404

    db = _FakeDB(objects={ios.Project: SimpleNamespace(id=1)})
    with pytest.raises(HTTPException) as bad:
        asyncio.run(ios.upload_ios_app(project_id=1, file=_Upload([], filename="a.apk"), db=db, current_user=_user()))
    assert bad.value.status_code == 400


def test_upload_ios_app_persists_metadata_and_uploads(monkeypatch):
    _no_access(monkeypatch)
    uploads = _record(monkeypatch, "upload_file")
    buckets = _record(monkeypatch, "ensure_bucket")
    monkeypatch.setattr(ios, "_read_ipa_metadata", lambda _path: {"bundle_id": "com.meta.app", "version_name": "2.0.1"})

    async def fake_save(_file):
        return "C:/tmp/does-not-exist.ipa", 2048

    monkeypatch.setattr(ios, "_save_upload", fake_save)
    upload = _Upload([], filename="Meta.ipa")
    db = _FakeDB(objects={ios.Project: SimpleNamespace(id=1)})
    result = asyncio.run(
        ios.upload_ios_app(
            project_id=1,
            file=upload,
            bundle_id=None,
            version_name=None,
            signing_identity=None,
            provisioning_profile=None,
            description=None,
            db=db,
            current_user=_user(),
        )
    )

    assert isinstance(result, ios.IosApp)
    assert result.bundle_id == "com.meta.app"
    assert result.version_name == "2.0.1"
    assert result.file_size == 2048
    assert result.uploaded_by == 7
    assert result.object_name.startswith("ios-apps/projects/1/")
    assert result.object_name.endswith("_Meta.ipa")
    assert buckets
    (args, kwargs) = uploads[0]
    assert args == (result.object_name, "C:/tmp/does-not-exist.ipa")
    assert kwargs == {"content_type": "application/octet-stream"}
    assert db.added == [result]
    assert upload.closed is True


def test_list_ios_apps_scopes_by_project(monkeypatch):
    access = _no_access(monkeypatch)
    scope_received = []

    def fake_scope(stmt, _col, _user_obj, project_id):
        scope_received.append(project_id)
        return stmt

    monkeypatch.setattr(ios, "scope_to_visible_projects", fake_scope)
    rows = [_app_row()]
    result = asyncio.run(ios.list_ios_apps(project_id=5, db=_FakeDB(results=[_Result(rows=rows)]), user=_user()))
    assert result == rows
    assert access == [(5, ios.ProjectRole.viewer)]
    assert scope_received == [5]

    empty = asyncio.run(ios.list_ios_apps(project_id=None, db=_FakeDB(results=[_Result()]), user=_user()))
    assert empty == []
    assert access == [(5, ios.ProjectRole.viewer)]
    assert scope_received == [5, None]


def test_get_ios_app_404_and_access_checked(monkeypatch):
    access = _no_access(monkeypatch)
    with pytest.raises(HTTPException) as missing:
        asyncio.run(ios.get_ios_app(app_id=41, db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404

    row = _app_row()
    result = asyncio.run(ios.get_ios_app(app_id=41, db=_FakeDB(objects={ios.IosApp: row}), user=_user()))
    assert result is row
    assert access == [(1, ios.ProjectRole.viewer)]


def test_update_ios_app_applies_fields(monkeypatch):
    _no_access(monkeypatch)
    row = _app_row()
    db = _FakeDB(objects={ios.IosApp: row})
    result = asyncio.run(ios.update_ios_app(app_id=41, body=IosAppUpdate(version_name="1.1.0"), db=db, user=_user()))
    assert result is row
    assert row.version_name == "1.1.0"
    assert db.commits == 1

    with pytest.raises(HTTPException) as missing:
        asyncio.run(ios.update_ios_app(app_id=99, body=IosAppUpdate(version_name="x"), db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404


def test_delete_ios_app_removes_row_even_on_storage_error(monkeypatch):
    _no_access(monkeypatch)

    def boom(*_args, **_kwargs):
        raise RuntimeError("minio unavailable")

    monkeypatch.setattr(ios, "delete_file", boom)
    row = _app_row()
    db = _FakeDB(objects={ios.IosApp: row})
    assert asyncio.run(ios.delete_ios_app(app_id=41, db=db, user=_user())) is None
    assert db.deleted == [row]
    assert db.commits == 1

    with pytest.raises(HTTPException) as missing:
        asyncio.run(ios.delete_ios_app(app_id=99, db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404


def test_download_ios_app_returns_presigned_url(monkeypatch):
    access = _no_access(monkeypatch)
    signed = _record(monkeypatch, "presigned_url", value="https://minio.local/signed")
    row = _app_row()
    result = asyncio.run(ios.download_ios_app(app_id=41, db=_FakeDB(objects={ios.IosApp: row}), user=_user()))
    assert result == {"url": "https://minio.local/signed", "filename": "Demo.ipa"}
    assert access == [(1, ios.ProjectRole.viewer)]
    (args, kwargs) = signed[0]
    assert args == (row.object_name,)
    assert kwargs == {"expires_seconds": 3600}

    with pytest.raises(HTTPException) as missing:
        asyncio.run(ios.download_ios_app(app_id=99, db=_FakeDB(), user=_user()))
    assert missing.value.status_code == 404


def test_save_upload_swallows_cleanup_oserror(monkeypatch):
    created = _track_tempfile(monkeypatch)
    monkeypatch.setattr(ios, "_MAX_IPA_SIZE", 4)
    real_remove = os.remove
    calls = []

    def failing_remove(path):
        calls.append(path)
        raise OSError("locked")

    monkeypatch.setattr(os, "remove", failing_remove)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ios._save_upload(_Upload([b"12345"])))
    assert exc.value.status_code == 413
    assert calls == [created[0]]
    assert os.path.exists(created[0])
    monkeypatch.undo()
    if os.path.exists(created[0]):
        real_remove(created[0])


def test_upload_ios_app_closes_file_when_save_fails(monkeypatch):
    _no_access(monkeypatch)

    async def failing_save(_file):
        raise HTTPException(status_code=413, detail="IPA 文件超过 500MB 限制")

    monkeypatch.setattr(ios, "_save_upload", failing_save)
    upload = _Upload([], filename="Big.ipa")
    db = _FakeDB(objects={ios.Project: SimpleNamespace(id=1)})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ios.upload_ios_app(
                project_id=1,
                file=upload,
                bundle_id=None,
                version_name=None,
                signing_identity=None,
                provisioning_profile=None,
                description=None,
                db=db,
                current_user=_user(),
            )
        )
    assert exc.value.status_code == 413
    assert upload.closed is True
