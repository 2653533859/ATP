"""cases/batch API 路由单元测试（Q13 延伸覆盖：批量删除/移动/CSV/ZIP 导入导出）。

伪造 DB 与 cases 包命名空间上的协作符号（write_audit_log / invalidate_stats_cache /
_generate_case_code / _get_module_for_case_code / _serialize_steps —— batch.py 通过
``import app.api.v1.cases as _cases`` 在调用点动态取属性，故桩打在包对象上），
运行真实路由逻辑：去重与部分不存在→skipped_ids、审计日志条件写入、CSV 导出
400 阶梯与 BOM/排序、ZIP 导入的 zip-bomb 守卫与逐条校验、导入模板往返。
"""

import asyncio
import io
import json
import sys
import types
import zipfile
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

from fastapi import HTTPException  # noqa: E402

from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

import app.api.v1.cases as cases_pkg  # noqa: E402
import app.api.v1.cases.batch as bt  # noqa: E402
from app.models.case import CaseStatus, CaseType, TestCase  # noqa: E402
from app.schemas.case import CaseBatchDeleteIn, CaseBatchMoveIn  # noqa: E402


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
        self._next_id = 900

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        return None

    async def execute(self, _query):
        return self.execute_results.pop(0) if self.execute_results else _FakeResult()


class _FakeUpload:
    def __init__(self, payload: bytes):
        self._payload = payload

    async def read(self):
        return self._payload


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    audit_calls = []
    invalidate_calls = []

    async def record_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    async def record_invalidate(*_a, **_kw):
        invalidate_calls.append(1)

    code_counter = {"n": 0}

    async def fake_case_code(_db, _module, _case_type):
        code_counter["n"] += 1
        return f"TC-{code_counter['n']:03d}"

    async def fake_module_for_code(_db, module_id):
        return _Obj(id=module_id, module_code="MOD")

    monkeypatch.setattr(cases_pkg, "write_audit_log", record_audit)
    monkeypatch.setattr(cases_pkg, "invalidate_stats_cache", record_invalidate)
    monkeypatch.setattr(cases_pkg, "_generate_case_code", fake_case_code)
    monkeypatch.setattr(cases_pkg, "_get_module_for_case_code", fake_module_for_code)
    monkeypatch.setattr(cases_pkg, "_serialize_steps", lambda steps: [{"step_no": i + 1} for i in range(len(steps))])
    return {"audit": audit_calls, "invalidate": invalidate_calls}


def _user(uid=9):
    return _Obj(id=uid, username="amy")


def _case(cid=1, module_id=3):
    return _Obj(
        id=cid,
        case_code=f"TC-{cid:03d}",
        name=f"用例{cid}",
        summary="摘要",
        description=None,
        case_type=CaseType.api,
        status=CaseStatus.draft,
        priority="P2",
        case_level="regression",
        review_status="pending",
        automation_status="auto",
        module_id=module_id,
        tags=["t1"],
        preconditions=[],
        postconditions=[],
        config={},
        steps=[],
        created_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )


async def _drain(resp) -> bytes:
    chunks = []
    async for chunk in resp.body_iterator:
        chunks.append(chunk.encode() if isinstance(chunk, str) else chunk)
    return b"".join(chunks)


def _make_zip(cases_payload, cases_name="cases.json") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(cases_name, json.dumps(cases_payload, ensure_ascii=False))
    return buffer.getvalue()


_VALID_ENTRY = {
    "name": "登录成功",
    "case_type": "api",
    "priority": "P1",
    "steps": [{"step_no": 1, "action": "发请求", "expected_result": "200"}],
}


# ── 批量删除 ────────────────────────────────────────────────


def test_batch_delete_dedups_and_reports_skipped(stubs):
    case = _case(1)
    db = _FakeDB(execute_results=[_FakeResult(rows=[case])])

    out = asyncio.run(
        bt.batch_delete_cases(body=CaseBatchDeleteIn(case_ids=[1, 1, 2]), db=db, current_user=_user())
    )

    assert (out.requested, out.processed, out.skipped_ids) == (2, 1, [2])
    assert db.deleted == [case]
    assert stubs["audit"][0]["action"] == "batch_delete"
    assert stubs["invalidate"] == [1]


def test_batch_delete_nothing_found_skips_audit(stubs):
    db = _FakeDB(execute_results=[_FakeResult(rows=[])])

    out = asyncio.run(bt.batch_delete_cases(body=CaseBatchDeleteIn(case_ids=[7, 8]), db=db, current_user=_user()))

    assert (out.processed, out.skipped_ids) == (0, [7, 8])
    assert stubs["audit"] == [] and stubs["invalidate"] == []


# ── 批量移动 ────────────────────────────────────────────────


def test_batch_move_target_module_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            bt.batch_move_cases(
                body=CaseBatchMoveIn(case_ids=[1], target_module_id=99), db=_FakeDB(), current_user=_user()
            )
        )
    assert exc.value.status_code == 404


def test_batch_move_skips_already_in_target(stubs):
    from app.models.project import Module

    already = _case(1, module_id=10)
    movable = _case(2, module_id=3)
    db = _FakeDB(
        objects={("Module", 10): _Obj(id=10)},
        execute_results=[_FakeResult(rows=[already, movable])],
    )
    assert Module.__name__ == "Module"

    out = asyncio.run(
        bt.batch_move_cases(
            body=CaseBatchMoveIn(case_ids=[1, 2, 5], target_module_id=10), db=db, current_user=_user()
        )
    )

    assert (out.requested, out.processed) == (3, 1)
    assert sorted(out.skipped_ids) == [1, 5]  # 5 不存在，1 已在目标模块
    assert movable.module_id == 10
    assert stubs["audit"][0]["action"] == "batch_move"


# ── CSV 导出 ────────────────────────────────────────────────


def test_batch_export_cases_error_ladder():
    for bad_ids, _why in (("1,abc", "非整数"), ("  ", "为空"), (",".join(map(str, range(1001))), "超上限")):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(bt.batch_export_cases(case_ids=bad_ids, db=_FakeDB(), _=_user()))
        assert exc.value.status_code == 400


def test_batch_export_cases_csv_bom_and_requested_order():
    db = _FakeDB(execute_results=[_FakeResult(rows=[_case(1), _case(2)])])

    resp = asyncio.run(bt.batch_export_cases(case_ids="2,1,404", db=db, _=_user()))
    body = asyncio.run(_drain(resp)).decode("utf-8")

    assert body.startswith("﻿")  # Excel 友好 BOM
    lines = [line for line in body.lstrip("﻿").splitlines() if line]
    assert lines[0].startswith("id,case_code,name")
    assert lines[1].startswith("2,") and lines[2].startswith("1,")  # 按请求顺序，404 忽略
    assert "attachment" in resp.headers["content-disposition"]


# ── ZIP 导入读取与校验 ──────────────────────────────────────


def test_read_cases_from_import_zip_error_ladder(monkeypatch):
    cases_of = {
        "空文件": b"",
        "非法ZIP": b"not-a-zip",
        "缺cases.json": _make_zip([_VALID_ENTRY], cases_name="other.json"),
        "非法JSON": None,
        "非数组": _make_zip({"not": "a list"}),
    }
    bad_json = io.BytesIO()
    with zipfile.ZipFile(bad_json, "w") as zf:
        zf.writestr("cases.json", "{broken json")
    cases_of["非法JSON"] = bad_json.getvalue()

    for _why, payload in cases_of.items():
        with pytest.raises(HTTPException) as exc:
            bt._read_cases_from_import_zip(payload)
        assert exc.value.status_code == 400

    # zip-bomb 守卫：解压后大小超限
    monkeypatch.setattr(bt, "_ZIP_IMPORT_MAX_DECOMPRESSED_BYTES", 1)
    with pytest.raises(HTTPException) as exc:
        bt._read_cases_from_import_zip(_make_zip([_VALID_ENTRY]))
    assert exc.value.status_code == 400 and "超过" in exc.value.detail


def test_validate_import_cases_collects_errors_and_preview():
    entries = [
        "not-a-dict",
        {"name": "x", "case_type": "nope"},
        {"name": "  ", "case_type": "api"},
        {"name": "y", "case_type": "api", "steps": "not-a-list"},
        _VALID_ENTRY,
    ]

    valid, errors, preview = bt._validate_import_cases(entries)

    assert len(valid) == 1 and valid[0]["name"] == "登录成功"
    assert len(errors) == 4 and errors[0].startswith("第 1 条")
    assert len(preview) == 1 and preview[0].row == 5 and preview[0].step_count == 1


# ── 模板 / 预览 ─────────────────────────────────────────────


def test_download_template_zip_roundtrip():
    resp = asyncio.run(bt.download_case_import_template(_=_user()))
    payload = asyncio.run(_drain(resp))

    archive = zipfile.ZipFile(io.BytesIO(payload))
    manifest = json.loads(archive.read("manifest.json"))
    cases = json.loads(archive.read("cases.json"))
    assert manifest["case_count"] == len(cases) == 1
    assert cases[0]["case_type"] == "api"


def test_preview_import_zip_mixed_entries():
    payload = _make_zip([_VALID_ENTRY, {"name": "", "case_type": "api"}])

    out = asyncio.run(bt.preview_case_import_zip(file=_FakeUpload(payload), _=_user()))

    assert (out.total, out.valid_count, out.invalid_count) == (2, 1, 1)
    assert out.preview_cases[0].name == "登录成功"


# ── ZIP 导出 ────────────────────────────────────────────────


def test_batch_export_zip_limit_and_roundtrip():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(bt.batch_export_cases_zip(case_ids=",".join(map(str, range(501))), db=_FakeDB(), _=_user()))
    assert exc.value.status_code == 400

    db = _FakeDB(execute_results=[_FakeResult(rows=[_case(1), _case(2)])])
    resp = asyncio.run(bt.batch_export_cases_zip(case_ids="2,1", db=db, _=_user()))
    archive = zipfile.ZipFile(io.BytesIO(asyncio.run(_drain(resp))))

    manifest = json.loads(archive.read("manifest.json"))
    cases = json.loads(archive.read("cases.json"))
    assert manifest["case_count"] == 2
    assert [c["case_code"] for c in cases] == ["TC-002", "TC-001"]  # 按请求顺序
    assert cases[0]["source_module_id"] == 3


# ── ZIP 导入 ────────────────────────────────────────────────


def test_batch_import_zip_module_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            bt.batch_import_cases_zip(
                target_module_id=99, file=_FakeUpload(_make_zip([_VALID_ENTRY])), db=_FakeDB(), current_user=_user()
            )
        )
    assert exc.value.status_code == 404


def test_batch_import_zip_creates_cases_and_steps(stubs):
    second = dict(_VALID_ENTRY, name="登出成功", steps=[])
    invalid = {"name": "", "case_type": "api"}
    db = _FakeDB(objects={("Module", 10): _Obj(id=10)})

    out = asyncio.run(
        bt.batch_import_cases_zip(
            target_module_id=10,
            file=_FakeUpload(_make_zip([_VALID_ENTRY, second, invalid])),
            db=db,
            current_user=_user(uid=9),
        )
    )

    created_cases = [obj for obj in db.added if isinstance(obj, TestCase)]
    assert out.imported == 2 and len(created_cases) == 2
    assert out.skipped_count == 1 and len(out.errors) == 1
    assert created_cases[0].case_code == "TC-001" and created_cases[0].creator_id == 9
    assert created_cases[0].module_id == 10 and created_cases[0].status == CaseStatus.draft
    step_rows = [obj for obj in db.added if not isinstance(obj, TestCase)]
    assert len(step_rows) == 1 and step_rows[0].case_id == created_cases[0].id
    assert stubs["invalidate"] == [1]


def test_batch_import_zip_per_entry_failure_recorded(stubs, monkeypatch):
    async def broken_case_code(_db, _module, _case_type):
        raise RuntimeError("code generator down")

    monkeypatch.setattr(cases_pkg, "_generate_case_code", broken_case_code)
    db = _FakeDB(objects={("Module", 10): _Obj(id=10)})

    out = asyncio.run(
        bt.batch_import_cases_zip(
            target_module_id=10, file=_FakeUpload(_make_zip([_VALID_ENTRY])), db=db, current_user=_user()
        )
    )

    assert out.imported == 0 and out.skipped_count == 1
    assert "code generator down" in out.errors[0]
    assert stubs["invalidate"] == []
