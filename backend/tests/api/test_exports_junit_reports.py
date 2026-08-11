"""exports 路由与报告构建器的单元测试（JUnit XML / 聚合 HTML / PDF / 缓存）。

与 test_exports_e1.py（模板/封面/ZIP）互补；本文件聚焦三级 JUnit 导出、
suite/plan 聚合报告构建、HTML 缓存命中路径与 PDF 路由。
"""

import asyncio
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import exports as exports_mod  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.models.case import RunStatus  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_report_rendering_from_access_checks(monkeypatch):
    async def allow(*_args, **_kwargs):
        return None

    monkeypatch.setattr(exports_mod, "_assert_test_run_access", allow)
    monkeypatch.setattr(exports_mod, "_assert_suite_run_access", allow)
    monkeypatch.setattr(exports_mod, "_assert_plan_run_access", allow)


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, step_rows=None):
        self.objects = dict(objects or {})
        self.step_rows = list(step_rows or [])

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    async def execute(self, _query):
        return _FakeResult(self.step_rows)


def _step(idx, status, name=None, error=None, duration=1500):
    return _Obj(step_index=idx, name=name or f"步骤{idx}", status=status, error_message=error, duration_ms=duration)


# ── run 级 JUnit ────────────────────────────────────────────


def test_export_run_junit_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(exports_mod.export_run_junit(404, db=_FakeDB()))
    assert exc.value.status_code == 404


def test_export_run_junit_renders_step_outcomes():
    run = _Obj(id=1, status=RunStatus.failed, duration_ms=4000, error_message=None)
    steps = [
        _step(0, RunStatus.passed),
        _step(1, RunStatus.failed, error="断言失败"),
        _step(2, RunStatus.error, error="连接异常"),
        _step(3, RunStatus.skipped),
    ]
    db = _FakeDB({("TestRun", 1): run}, step_rows=steps)

    response = asyncio.run(exports_mod.export_run_junit(1, db=db))

    root = ET.fromstring(response.body)
    suite = root.find("testsuite")
    assert suite.get("tests") == "4" and suite.get("failures") == "1" and suite.get("errors") == "1"
    cases = suite.findall("testcase")
    assert cases[1].find("failure").get("message") == "断言失败"
    assert cases[2].find("error").get("message") == "连接异常"
    assert cases[3].find("skipped") is not None
    assert "run-1-junit.xml" in response.headers["Content-Disposition"]


@pytest.mark.parametrize(
    ("run_status", "element"),
    [(RunStatus.failed, "failure"), (RunStatus.error, "error"), (RunStatus.skipped, "skipped")],
)
def test_export_run_junit_synthesizes_case_for_stepless_runs(run_status, element):
    run = _Obj(id=2, status=run_status, duration_ms=100, error_message="run 级失败")
    db = _FakeDB({("TestRun", 2): run}, step_rows=[])

    response = asyncio.run(exports_mod.export_run_junit(2, db=db))

    root = ET.fromstring(response.body)
    suite = root.find("testsuite")
    assert suite.get("tests") == "1"
    testcase = suite.find("testcase")
    assert testcase.find(element) is not None


# ── suite 级 JUnit ──────────────────────────────────────────


def test_export_suite_run_junit_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(exports_mod.export_suite_run_junit(404, db=_FakeDB()))
    assert exc.value.status_code == 404


def test_export_suite_run_junit_uses_summary_and_actual_durations():
    suite_run = _Obj(
        id=5,
        duration_ms=9000,
        result_summary={"total": 3, "failed": 1, "error": 1},
        case_run_ids=[
            {"case_id": 1, "case_name": "登录", "status": "passed", "run_id": 11},
            {"case_id": 2, "case_name": "下单", "status": "failed", "run_id": None, "error": "断言"},
            {"case_id": 3, "status": "skipped"},
        ],
    )
    actual_run = _Obj(id=11, duration_ms=2000)
    db = _FakeDB({("SuiteRun", 5): suite_run, ("TestRun", 11): actual_run})

    response = asyncio.run(exports_mod.export_suite_run_junit(5, db=db))

    suite = ET.fromstring(response.body).find("testsuite")
    assert suite.get("tests") == "3" and suite.get("failures") == "1"
    cases = suite.findall("testcase")
    assert cases[0].get("time") == "2.000"
    assert cases[1].find("failure").get("message") == "断言"
    assert cases[2].get("name") == "Case-3"
    assert cases[2].find("skipped") is not None


# ── plan 级 JUnit ───────────────────────────────────────────


def test_export_plan_run_junit_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(exports_mod.export_plan_run_junit(404, db=_FakeDB()))
    assert exc.value.status_code == 404


def test_export_plan_run_junit_covers_missing_and_real_suites():
    plan_run = _Obj(
        id=7,
        suite_run_ids=[
            {"suite_id": 1, "suite_name": "冒烟", "suite_run_id": None, "error": "套件不存在"},
            {"suite_id": 2, "suite_name": "回归", "suite_run_id": 21},
            {"suite_id": 3, "suite_name": "幽灵", "suite_run_id": 99},  # SuiteRun 查不到 → 跳过
        ],
    )
    suite_run = _Obj(
        id=21,
        duration_ms=5000,
        result_summary={"total": 2, "failed": 1, "error": 0},
        case_run_ids=[
            {"case_id": 1, "case_name": "登录", "status": "failed", "run_id": 31, "error": "超时"},
            {"case_id": 2, "case_name": "登出", "status": "passed"},
        ],
    )
    db = _FakeDB({("PlanRun", 7): plan_run, ("SuiteRun", 21): suite_run, ("TestRun", 31): _Obj(id=31, duration_ms=800)})

    response = asyncio.run(exports_mod.export_plan_run_junit(7, db=db))

    root = ET.fromstring(response.body)
    suites = root.findall("testsuite")
    assert len(suites) == 2  # 幽灵套件被跳过
    assert suites[0].get("name") == "冒烟" and suites[0].get("errors") == "1"
    assert suites[0].find("testcase").find("error").get("message") == "套件不存在"
    regression_cases = suites[1].findall("testcase")
    assert regression_cases[0].find("failure").get("message") == "超时"
    assert regression_cases[0].get("time") == "0.800"


# ── 纯 helper ───────────────────────────────────────────────


def test_normalize_status_format_duration_and_merge_summary():
    assert exports_mod._normalize_status(RunStatus.passed) == "passed"
    assert exports_mod._normalize_status(None) == "pending"
    assert exports_mod._format_duration(None) == "-"
    assert exports_mod._format_duration(2500) == "2.5s"
    assert exports_mod._format_duration("oops") == "-"
    assert exports_mod._merge_summary(None, 4) == {"total": 4, "passed": 0, "failed": 0, "error": 0}
    assert exports_mod._merge_summary({"total": 0, "passed": 2}, 3) == {
        "total": 3,
        "passed": 2,
        "failed": 0,
        "error": 0,
    }


def test_report_cache_read_write_swallow_storage_errors(monkeypatch):
    def broken_read(_name):
        raise RuntimeError("minio down")

    monkeypatch.setattr(exports_mod, "read_bytes", broken_read)
    assert exports_mod._try_read_cached_report("reports/x.html") is None

    def broken_upload(*_a, **_kw):
        raise RuntimeError("minio down")

    monkeypatch.setattr(sys.modules["app.core.minio_client"], "upload_bytes", broken_upload, raising=False)
    exports_mod._try_write_cached_report("reports/x.html", "<html/>")  # 不抛异常即通过


# ── 聚合报告 HTML ───────────────────────────────────────────


def _dt():
    from datetime import datetime, timezone

    return datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc)


def test_build_suite_run_report_html_renders_case_rows():
    suite_run = _Obj(
        id=5,
        suite_id=2,
        status=RunStatus.failed,
        duration_ms=9000,
        created_at=_dt(),
        error_message=None,
        result_summary={"total": 2, "passed": 1, "failed": 1, "error": 0},
        case_run_ids=[
            {"case_id": 1, "case_name": "登录", "status": "passed", "run_id": 11},
            {"case_id": 2, "case_name": "下单", "status": "failed", "error": "价格断言不符"},
        ],
    )
    db = _FakeDB({("TestRun", 11): _Obj(id=11, duration_ms=1200, environment="staging")})

    html = asyncio.run(exports_mod._build_suite_run_report_html(db, suite_run))

    assert "套件执行报告 #5" in html
    assert "登录" in html and "staging" in html
    assert "价格断言不符" in html


def test_build_plan_run_report_html_aggregates_suites():
    plan_run = _Obj(
        id=9,
        plan_id=3,
        status=RunStatus.failed,
        duration_ms=20000,
        created_at=_dt(),
        suite_run_ids=[
            {"suite_id": 2, "suite_name": "回归", "suite_run_id": 21},
            {"suite_id": 4, "suite_name": "缺失", "suite_run_id": None, "error": "套件不存在"},
        ],
    )
    suite_run = _Obj(
        id=21,
        status=RunStatus.failed,
        duration_ms=5000,
        error_message=None,
        result_summary={"total": 2, "passed": 1, "failed": 1, "error": 0},
        case_run_ids=[
            {"case_id": 1, "case_name": "登录", "status": "passed", "run_id": 31, "duration_ms": 700},
            {"case_id": 2, "case_name": "支付", "status": "failed", "error": "500"},
        ],
    )
    db = _FakeDB({("SuiteRun", 21): suite_run, ("TestRun", 31): _Obj(id=31, environment="prod-like")})

    html = asyncio.run(exports_mod._build_plan_run_report_html(db, plan_run))

    assert "计划执行报告 #9" in html
    assert "回归" in html and "缺失" in html
    assert "套件不存在" in html
    assert "prod-like" in html


# ── HTML/PDF 路由 ───────────────────────────────────────────


def _run_with_case_db(run_id=1):
    run = _Obj(id=run_id, case_id=10, status=RunStatus.passed, duration_ms=1000, updated_at=_dt(), created_at=_dt())
    case = _Obj(id=10, name="登录用例", case_type=types.SimpleNamespace(value="api"))
    return run, _FakeDB({("TestRun", run_id): run, ("TestCase", 10): case}, step_rows=[])


def test_export_run_html_cache_hit_short_circuits(monkeypatch):
    run, db = _run_with_case_db()
    monkeypatch.setattr(exports_mod, "_try_read_cached_report", lambda _name: b"<html>cached</html>")

    response = asyncio.run(exports_mod.export_run_html(1, db=db))

    assert response.headers["X-Atp-Cache"] == "hit"
    assert response.body == b"<html>cached</html>"


def test_export_run_html_cache_miss_builds_and_writes(monkeypatch):
    run, db = _run_with_case_db()
    written = {}
    monkeypatch.setattr(exports_mod, "_try_read_cached_report", lambda _name: None)
    monkeypatch.setattr(exports_mod, "_try_write_cached_report", lambda name, html: written.update({name: html}))

    response = asyncio.run(exports_mod.export_run_html(1, db=db))

    assert response.headers["X-Atp-Cache"] == "miss"
    assert "登录用例" in list(written.values())[0]


def test_export_run_html_404():
    with pytest.raises(HTTPException):
        asyncio.run(exports_mod.export_run_html(404, db=_FakeDB()))


def test_export_run_pdf_renders_via_playwright_boundary(monkeypatch):
    _run, db = _run_with_case_db(3)

    async def fake_render(html):
        assert "登录用例" in html
        return b"%PDF-fake"

    monkeypatch.setattr(exports_mod, "_render_pdf_from_html", fake_render)

    response = asyncio.run(exports_mod.export_run_pdf(3, db=db))

    assert response.body == b"%PDF-fake"
    assert response.media_type == "application/pdf"

    with pytest.raises(HTTPException):
        asyncio.run(exports_mod.export_run_pdf(404, db=_FakeDB()))


def test_suite_and_plan_html_pdf_routes(monkeypatch):
    suite_run = _Obj(id=5, suite_id=2, status=RunStatus.passed, duration_ms=100, created_at=_dt(), case_run_ids=[])
    plan_run = _Obj(id=9, plan_id=3, status=RunStatus.passed, duration_ms=100, created_at=_dt(), suite_run_ids=[])
    db = _FakeDB({("SuiteRun", 5): suite_run, ("PlanRun", 9): plan_run})

    async def fake_render(_html):
        return b"%PDF-agg"

    monkeypatch.setattr(exports_mod, "_render_pdf_from_html", fake_render)

    assert b"#5" in asyncio.run(exports_mod.export_suite_run_html(5, db=db)).body
    assert asyncio.run(exports_mod.export_suite_run_pdf(5, db=db)).body == b"%PDF-agg"
    assert b"#9" in asyncio.run(exports_mod.export_plan_run_html(9, db=db)).body
    assert asyncio.run(exports_mod.export_plan_run_pdf(9, db=db)).body == b"%PDF-agg"

    for route in (
        exports_mod.export_suite_run_html,
        exports_mod.export_suite_run_pdf,
        exports_mod.export_plan_run_html,
        exports_mod.export_plan_run_pdf,
    ):
        with pytest.raises(HTTPException):
            asyncio.run(route(404, db=_FakeDB()))
