"""E.1 报告导出增强测试：template / cover / MinIO 缓存 key / 批量 ZIP."""

import asyncio
import io
import sys
import types
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules.setdefault("app.core.database", types.SimpleNamespace(get_db=lambda: None))
sys.modules.setdefault(
    "app.api.deps",
    types.SimpleNamespace(
        get_current_user=lambda: None,
        require_engineer=lambda: None,
        require_admin=lambda: None,
    ),
)
_minio_stub = sys.modules.setdefault(
    "app.core.minio_client",
    types.SimpleNamespace(
        read_bytes=lambda *_a, **_kw: b"",
        upload_bytes=lambda *_a, **_kw: None,
        list_objects=lambda *_a, **_kw: [],
        delete_file=lambda *_a, **_kw: None,
    ),
)
# 已存在但缺失字段时补齐
for _name, _fn in (
    ("read_bytes", lambda *_a, **_kw: b""),
    ("upload_bytes", lambda *_a, **_kw: None),
):
    if not hasattr(_minio_stub, _name):
        setattr(_minio_stub, _name, _fn)


from app.api.v1 import exports as exports_mod
from app.models.bootstrap import load_all_models

load_all_models()

from app.models.case import CaseType, RunStatus, StepResult, TestCase, TestRun


def _now():
    return datetime.now(timezone.utc)


def _make_run(run_id=1, updated_ts="20260521010203") -> TestRun:
    run = TestRun(
        id=run_id,
        case_id=10,
        triggered_by=1,
        status=RunStatus.passed,
        environment="dev",
        duration_ms=1500,
        error_message=None,
        result_summary={},
    )
    run.created_at = _now()
    run.updated_at = datetime.strptime(updated_ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return run


def _make_step(idx=1) -> StepResult:
    step = StepResult(
        id=idx,
        run_id=1,
        step_index=idx,
        name=f"step-{idx}",
        status=RunStatus.passed,
        duration_ms=400,
        request_data={"url": "/api/x"},
        response_data={"ok": True},
        screenshot_url=None,
        error_message=None,
    )
    step.created_at = _now()
    step.updated_at = _now()
    return step


def test_build_report_html_summary_skips_request_response():
    run = _make_run()
    steps = [_make_step(1), _make_step(2)]
    html = asyncio.run(
        exports_mod._build_report_html(
            run,
            steps,
            "case-summary",
            case_type="api",
            template_mode="summary",
        )
    )
    # summary 模式下，表头不应有 "截图" 列
    assert "截图" not in html
    assert "step-1" in html
    assert "(简洁版)" in html


def test_build_report_html_full_includes_screenshot_column():
    run = _make_run()
    steps = [_make_step(1)]
    html = asyncio.run(exports_mod._build_report_html(run, steps, "case-full", case_type="api", template_mode="full"))
    assert "截图" in html


def test_build_report_html_renders_cover_block():
    run = _make_run()
    html = asyncio.run(
        exports_mod._build_report_html(
            run,
            [],
            "case-name",
            case_type="api",
            cover_title="ATP 自动化测试报告",
            cover_logo_url="https://example.com/logo.png",
        )
    )
    assert "ATP 自动化测试报告" in html
    assert "https://example.com/logo.png" in html


def test_build_report_html_embeds_video_when_url_present():
    """P1.1：当 run.result_summary.video_url 存在时，HTML 报告应嵌入 <video> 标签。"""
    run = _make_run()
    run.result_summary = {"video_url": "https://minio.local/videos/runs/1/recording.webm"}
    html = asyncio.run(exports_mod._build_report_html(run, [], "case-name", case_type="web"))
    assert "<video" in html
    assert "https://minio.local/videos/runs/1/recording.webm" in html
    assert "执行录像" in html


def test_build_report_html_omits_video_when_url_absent():
    run = _make_run()
    run.result_summary = {}
    html = asyncio.run(exports_mod._build_report_html(run, [], "case-name", case_type="web"))
    assert "<video" not in html
    assert "执行录像" not in html


def test_build_report_html_omits_video_when_include_video_false():
    """PDF 路径走 include_video=False，即使有 video_url 也不应嵌入。"""
    run = _make_run()
    run.result_summary = {"video_url": "https://x.com/v.webm"}
    html = asyncio.run(exports_mod._build_report_html(run, [], "case-name", case_type="web", include_video=False))
    assert "<video" not in html


def test_report_cache_object_name_varies_with_template_and_cover():
    run = _make_run()
    a = exports_mod._report_cache_object_name(run, "full", "")
    b = exports_mod._report_cache_object_name(run, "summary", "")
    c = exports_mod._report_cache_object_name(run, "full", "MyCover|")
    assert a != b
    assert a != c
    assert a.startswith("reports/run-1/")


def test_report_cache_object_name_changes_when_run_updated_at_changes():
    r1 = _make_run(updated_ts="20260521010203")
    r2 = _make_run(updated_ts="20260521010204")
    assert exports_mod._report_cache_object_name(r1, "full", "") != exports_mod._report_cache_object_name(
        r2, "full", ""
    )


class _BatchDB:
    """伪 db：按 run_id 返回 run，按 case_id 返回 case，steps 返回空列表。"""

    def __init__(self, runs):
        self._runs = runs

    async def get(self, model, pk):
        name = getattr(model, "__name__", "")
        if name == "TestRun":
            return self._runs.get(pk)
        if name == "TestCase":
            case = TestCase(
                id=pk,
                name=f"case-{pk}",
                case_code=f"ATP-X-API-{pk:04d}",
                summary=f"case-{pk}",
                case_type=CaseType.api,
                module_id=1,
                creator_id=1,
                config={},
            )
            case.created_at = _now()
            case.updated_at = _now()
            return case
        return None

    async def execute(self, _stmt):
        class _R:
            def scalars(self_inner):
                class _S:
                    def all(s):
                        return []

                return _S()

        return _R()


def test_export_runs_zip_packages_html_files_and_records_missing():
    runs = {1: _make_run(1), 2: _make_run(2)}  # run_id 99 不存在
    db = _BatchDB(runs)
    payload = {"run_ids": [1, 2, 99], "template": "summary"}
    response = asyncio.run(exports_mod.export_runs_zip(payload=payload, db=db))
    assert response.media_type == "application/zip"

    buf = io.BytesIO(response.body)
    with zipfile.ZipFile(buf) as zf:
        names = set(zf.namelist())
        assert "run-1-report.html" in names
        assert "run-2-report.html" in names
        assert "_missing.txt" in names
        missing_text = zf.read("_missing.txt").decode()
        assert "99" in missing_text


def test_export_runs_zip_rejects_empty_and_oversized():
    db = _BatchDB({})
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        asyncio.run(exports_mod.export_runs_zip(payload={"run_ids": []}, db=db))
    assert exc.value.status_code == 400

    too_many = {"run_ids": list(range(1, 60))}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(exports_mod.export_runs_zip(payload=too_many, db=db))
    assert exc.value.status_code == 400


def test_export_runs_zip_rejects_invalid_template():
    db = _BatchDB({})
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        asyncio.run(exports_mod.export_runs_zip(payload={"run_ids": [1], "template": "weird"}, db=db))
    assert exc.value.status_code == 400
