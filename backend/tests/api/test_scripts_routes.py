"""scripts API 路由单元测试（Q15-05：此前 0%）。

直接调用路由函数：FakeDB 承载用例对象，MinIO 边界（ensure_bucket / upload_bytes /
read_bytes / delete_file）按测试注入，大小限制、类型限制与 `case.config` 的读写走
真实现。重点在两条容易写错的地方：脚本路径必须落进 `case.config` 才能被执行器找到；
MinIO 读写失败时 GET/DELETE 不能把整个页面打崩。
"""

from __future__ import annotations

import asyncio
import sys
import types

import pytest
from fastapi import HTTPException

# `backend/tests/api/conftest.py` 会把 MinIO stub 的字段补齐，但那只在收集本目录时
# 跑一次；此后有若干测试文件直接 `sys.modules["app.core.minio_client"] = ...` 换成
# 更窄的 stub，于是本文件（按字母序在它们之后）导入被测路由时会因为缺 delete_file
# 而 ImportError。这里按仓库既有做法只补缺失符号，不覆盖已有值。
_minio = sys.modules.get("app.core.minio_client")
if _minio is not None:
    for _name, _value in (
        ("ensure_bucket", lambda *_a, **_kw: None),
        ("upload_bytes", lambda *_a, **_kw: None),
        ("read_bytes", lambda *_a, **_kw: b""),
        ("delete_file", lambda *_a, **_kw: None),
    ):
        if not hasattr(_minio, _name):
            setattr(_minio, _name, _value)

from app.api.v1 import scripts as scripts_module  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.case import CaseType  # noqa: E402

load_all_models()


class _FakeDB:
    def __init__(self, case=None):
        self._case = case
        self.commits = 0

    async def get(self, _model, _pk):
        return self._case

    async def commit(self):
        self.commits += 1


class _FakeUpload:
    def __init__(self, content: bytes):
        self._content = content

    async def read(self):
        return self._content


def _case(case_type=CaseType.web, config=None):
    return types.SimpleNamespace(id=5, case_type=case_type, config=config)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def minio(monkeypatch):
    """记录 MinIO 调用，默认成功。"""
    calls: dict = {"ensure": 0, "uploaded": [], "deleted": [], "read": {}}

    monkeypatch.setattr(scripts_module, "ensure_bucket", lambda: calls.__setitem__("ensure", calls["ensure"] + 1))
    monkeypatch.setattr(
        scripts_module,
        "upload_bytes",
        lambda name, content, content_type=None: calls["uploaded"].append((name, content, content_type)),
    )
    monkeypatch.setattr(scripts_module, "delete_file", lambda name: calls["deleted"].append(name))
    monkeypatch.setattr(scripts_module, "read_bytes", lambda name: calls["read"].get(name, b""))

    async def allow_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(scripts_module, "_assert_case_script_access", allow_access)
    return calls


def test_object_name_is_namespaced_per_case():
    assert scripts_module._script_object_name(42) == "scripts/cases/42/script.py"


def test_upload_stores_the_object_and_records_the_path_in_the_case_config(minio):
    case = _case(config={"browser": "chromium"})
    db = _FakeDB(case)

    result = _run(scripts_module.upload_script(5, _FakeUpload(b"print('hi')"), db, None))

    assert result == {"script_path": "scripts/cases/5/script.py", "size": 11}
    assert minio["ensure"] == 1, "上传前必须确保 bucket 存在，否则首次部署会失败"
    assert minio["uploaded"] == [("scripts/cases/5/script.py", b"print('hi')", "text/x-python")]
    # 既有配置项必须保留，执行器靠 script_path 找脚本
    assert case.config == {"browser": "chromium", "script_path": "scripts/cases/5/script.py"}
    assert db.commits == 1


def test_upload_initializes_a_missing_config(minio):
    case = _case(config=None)

    _run(scripts_module.upload_script(5, _FakeUpload(b"x"), _FakeDB(case), None))

    assert case.config == {"script_path": "scripts/cases/5/script.py"}


def test_upload_rejects_a_missing_case(minio):
    with pytest.raises(HTTPException) as excinfo:
        _run(scripts_module.upload_script(5, _FakeUpload(b"x"), _FakeDB(None), None))

    assert excinfo.value.status_code == 404
    assert minio["uploaded"] == []


@pytest.mark.parametrize("case_type", [CaseType.api, CaseType.graphql, CaseType.websocket, CaseType.grpc])
def test_upload_rejects_non_script_case_types(minio, case_type):
    with pytest.raises(HTTPException) as excinfo:
        _run(scripts_module.upload_script(5, _FakeUpload(b"x"), _FakeDB(_case(case_type)), None))

    assert excinfo.value.status_code == 400
    assert minio["uploaded"] == [], "类型不符时不应产生 MinIO 对象"


@pytest.mark.parametrize("case_type", [CaseType.web, CaseType.android])
def test_upload_accepts_both_script_case_types(minio, case_type):
    _run(scripts_module.upload_script(5, _FakeUpload(b"x"), _FakeDB(_case(case_type)), None))

    assert len(minio["uploaded"]) == 1


def test_upload_enforces_the_one_megabyte_limit(minio):
    oversized = b"a" * (1 * 1024 * 1024 + 1)

    with pytest.raises(HTTPException) as excinfo:
        _run(scripts_module.upload_script(5, _FakeUpload(oversized), _FakeDB(_case()), None))

    assert excinfo.value.status_code == 413
    assert minio["uploaded"] == [], "超限文件不得落盘"


def test_upload_accepts_a_file_exactly_at_the_limit(minio):
    at_limit = b"a" * (1 * 1024 * 1024)

    result = _run(scripts_module.upload_script(5, _FakeUpload(at_limit), _FakeDB(_case()), None))

    assert result["size"] == 1 * 1024 * 1024


def test_get_returns_the_decoded_script(minio):
    minio["read"]["scripts/cases/5/script.py"] = "print('héllo')".encode("utf-8")
    case = _case(config={"script_path": "scripts/cases/5/script.py"})

    result = _run(scripts_module.get_script(5, _FakeDB(case), None))

    assert result == {
        "content": "print('héllo')",
        "exists": True,
        "script_path": "scripts/cases/5/script.py",
    }


def test_get_replaces_undecodable_bytes_instead_of_failing(monkeypatch, minio):
    monkeypatch.setattr(scripts_module, "read_bytes", lambda _name: b"\xff\xfe")
    case = _case(config={"script_path": "scripts/cases/5/script.py"})

    result = _run(scripts_module.get_script(5, _FakeDB(case), None))

    assert result["exists"] is True
    assert "�" in result["content"]


def test_get_reports_absent_when_no_script_was_uploaded(minio):
    for config in (None, {}, {"script_path": ""}):
        result = _run(scripts_module.get_script(5, _FakeDB(_case(config=config)), None))

        assert result == {"content": "", "exists": False}


def test_get_degrades_gracefully_when_minio_is_unreachable(monkeypatch, minio):
    """对象丢失或 MinIO 挂掉时返回 exists=False，而不是 500 把编辑器打崩。"""

    def boom(_name):
        raise RuntimeError("minio down")

    monkeypatch.setattr(scripts_module, "read_bytes", boom)
    case = _case(config={"script_path": "scripts/cases/5/script.py"})

    assert _run(scripts_module.get_script(5, _FakeDB(case), None)) == {"content": "", "exists": False}


def test_get_rejects_a_missing_case(minio):
    with pytest.raises(HTTPException) as excinfo:
        _run(scripts_module.get_script(5, _FakeDB(None), None))

    assert excinfo.value.status_code == 404


def test_delete_removes_the_object_and_the_config_key(minio):
    case = _case(config={"script_path": "scripts/cases/5/script.py", "browser": "chromium"})
    db = _FakeDB(case)

    _run(scripts_module.delete_script(5, db, None))

    assert minio["deleted"] == ["scripts/cases/5/script.py"]
    assert case.config == {"browser": "chromium"}, "只摘掉 script_path，其余配置保留"
    assert db.commits == 1


def test_delete_still_clears_the_config_when_minio_delete_fails(monkeypatch, minio):
    """对象已经不在了也要把 config 里的悬空引用清掉，否则执行器会一直找不到脚本。"""

    def boom(_name):
        raise RuntimeError("no such key")

    monkeypatch.setattr(scripts_module, "delete_file", boom)
    case = _case(config={"script_path": "scripts/cases/5/script.py"})
    db = _FakeDB(case)

    _run(scripts_module.delete_script(5, db, None))

    assert case.config == {}
    assert db.commits == 1


def test_delete_is_a_noop_without_a_script(minio):
    case = _case(config={})
    db = _FakeDB(case)

    _run(scripts_module.delete_script(5, db, None))

    assert minio["deleted"] == []
    assert db.commits == 0


def test_delete_rejects_a_missing_case(minio):
    with pytest.raises(HTTPException) as excinfo:
        _run(scripts_module.delete_script(5, _FakeDB(None), None))

    assert excinfo.value.status_code == 404
