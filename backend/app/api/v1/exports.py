"""
导出接口

GET /runs/{id}/junit          单用例执行结果 JUnit XML
GET /suite-runs/{id}/junit    套件执行结果 JUnit XML
GET /plan-runs/{id}/junit     计划执行结果 JUnit XML
GET /runs/{id}/export/html    执行报告 HTML（内嵌截图）
GET /runs/{id}/export/pdf     执行报告 PDF
POST /runs/export/zip         批量导出多个 run 的 HTML 报告为 ZIP

E.1 模板可选：?template=summary|full（默认 full；summary 不渲染步骤请求/响应）
E.1 自定义封面：?cover_title=xxx&cover_logo_url=https://...
E.1 报告缓存：MinIO key reports/run-{id}/{template}-{updated_at}.html，命中直接返回
"""

import base64
import hashlib
import io
import logging
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response
from jinja2 import Environment, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.minio_client import read_bytes
from app.core.object_refs import extract_object_name
from app.models.case import TestRun, StepResult, TestCase
from app.models.suite import SuiteRun
from app.models.plan import PlanRun
from app.api.deps import get_current_user

router = APIRouter(tags=["导出"])


@router.get("/runs/{run_id}/junit")
async def export_run_junit(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """导出单用例执行结果为 JUnit XML"""
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    result = await db.execute(select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.step_index))
    steps = result.scalars().all()
    run_status = getattr(run.status, "value", str(run.status))
    has_run_level_issue = not steps and run_status in {"failed", "error", "skipped"}

    tests_count = len(steps)
    failures_count = sum(1 for s in steps if s.status.value == "failed")
    errors_count = sum(1 for s in steps if s.status.value == "error")
    if has_run_level_issue:
        tests_count = 1
        if run_status == "failed":
            failures_count = 1
        elif run_status == "error":
            errors_count = 1

    root = ET.Element("testsuites")
    suite_el = ET.SubElement(
        root,
        "testsuite",
        {
            "name": f"TestRun-{run.id}",
            "tests": str(tests_count),
            "failures": str(failures_count),
            "errors": str(errors_count),
            "time": f"{(run.duration_ms or 0) / 1000:.3f}",
        },
    )

    if has_run_level_issue:
        tc = ET.SubElement(
            suite_el,
            "testcase",
            {
                "name": f"Run-{run.id}",
                "classname": f"TestRun-{run.id}",
                "time": f"{(run.duration_ms or 0) / 1000:.3f}",
            },
        )
        message = run.error_message or f"Run status: {run_status}"
        if run_status == "failed":
            fail = ET.SubElement(tc, "failure", {"message": message})
            fail.text = message
        elif run_status == "error":
            err = ET.SubElement(tc, "error", {"message": message})
            err.text = message
        elif run_status == "skipped":
            ET.SubElement(tc, "skipped")
    else:
        for step in steps:
            tc = ET.SubElement(
                suite_el,
                "testcase",
                {
                    "name": step.name or f"Step-{step.step_index}",
                    "classname": f"TestRun-{run.id}",
                    "time": f"{(step.duration_ms or 0) / 1000:.3f}",
                },
            )
            if step.status.value == "failed":
                fail = ET.SubElement(tc, "failure", {"message": step.error_message or "Assertion failed"})
                fail.text = step.error_message or ""
            elif step.status.value == "error":
                err = ET.SubElement(tc, "error", {"message": step.error_message or "Error"})
                err.text = step.error_message or ""
            elif step.status.value == "skipped":
                ET.SubElement(tc, "skipped")

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=run-{run_id}-junit.xml"},
    )


@router.get("/suite-runs/{run_id}/junit")
async def export_suite_run_junit(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """导出套件执行结果为 JUnit XML"""
    suite_run = await db.get(SuiteRun, run_id)
    if not suite_run:
        raise HTTPException(status_code=404, detail="套件执行记录不存在")

    root = ET.Element("testsuites")
    case_runs = suite_run.case_run_ids or []
    summary = suite_run.result_summary or {}

    suite_el = ET.SubElement(
        root,
        "testsuite",
        {
            "name": f"SuiteRun-{suite_run.id}",
            "tests": str(summary.get("total", len(case_runs))),
            "failures": str(summary.get("failed", 0)),
            "errors": str(summary.get("error", 0)),
            "time": f"{(suite_run.duration_ms or 0) / 1000:.3f}",
        },
    )

    for item in case_runs:
        case_name = item.get("case_name", f"Case-{item.get('case_id', '?')}")
        case_status = item.get("status", "error")
        case_run_id = item.get("run_id")

        # 尝试获取实际 TestRun 的耗时
        duration = 0
        if case_run_id:
            actual_run = await db.get(TestRun, case_run_id)
            if actual_run:
                duration = actual_run.duration_ms or 0

        tc = ET.SubElement(
            suite_el,
            "testcase",
            {
                "name": case_name,
                "classname": f"SuiteRun-{suite_run.id}",
                "time": f"{duration / 1000:.3f}",
            },
        )
        if case_status == "failed":
            ET.SubElement(tc, "failure", {"message": item.get("error", "Failed")})
        elif case_status == "error":
            ET.SubElement(tc, "error", {"message": item.get("error", "Error")})
        elif case_status == "skipped":
            ET.SubElement(tc, "skipped")

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=suite-run-{run_id}-junit.xml"},
    )


@router.get("/plan-runs/{run_id}/junit")
async def export_plan_run_junit(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """导出计划执行结果为 JUnit XML（包含所有套件）"""
    plan_run = await db.get(PlanRun, run_id)
    if not plan_run:
        raise HTTPException(status_code=404, detail="计划执行记录不存在")

    root = ET.Element("testsuites")
    suite_runs = plan_run.suite_run_ids or []

    for item in suite_runs:
        suite_name = item.get("suite_name", f"Suite-{item.get('suite_id', '?')}")
        suite_run_id = item.get("suite_run_id")

        if not suite_run_id:
            # 套件不存在，生成一个 error testcase
            ts = ET.SubElement(
                root,
                "testsuite",
                {
                    "name": suite_name,
                    "tests": "1",
                    "errors": "1",
                    "failures": "0",
                    "time": "0",
                },
            )
            tc = ET.SubElement(ts, "testcase", {"name": suite_name, "classname": f"PlanRun-{run_id}"})
            ET.SubElement(tc, "error", {"message": item.get("error", "Suite not found")})
            continue

        sr = await db.get(SuiteRun, suite_run_id)
        if not sr:
            continue

        case_runs = sr.case_run_ids or []
        sr_summary = sr.result_summary or {}

        ts = ET.SubElement(
            root,
            "testsuite",
            {
                "name": suite_name,
                "tests": str(sr_summary.get("total", len(case_runs))),
                "failures": str(sr_summary.get("failed", 0)),
                "errors": str(sr_summary.get("error", 0)),
                "time": f"{(sr.duration_ms or 0) / 1000:.3f}",
            },
        )

        for cr in case_runs:
            case_name = cr.get("case_name", f"Case-{cr.get('case_id', '?')}")
            case_status = cr.get("status", "error")
            duration = 0
            if cr.get("run_id"):
                actual_run = await db.get(TestRun, cr["run_id"])
                if actual_run:
                    duration = actual_run.duration_ms or 0

            tc = ET.SubElement(
                ts,
                "testcase",
                {
                    "name": case_name,
                    "classname": suite_name,
                    "time": f"{duration / 1000:.3f}",
                },
            )
            if case_status == "failed":
                ET.SubElement(tc, "failure", {"message": cr.get("error", "Failed")})
            elif case_status == "error":
                ET.SubElement(tc, "error", {"message": cr.get("error", "Error")})
            elif case_status == "skipped":
                ET.SubElement(tc, "skipped")

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=plan-run-{run_id}-junit.xml"},
    )


# ── HTML / PDF 报告导出 ─────────────────────────────────────

logger = logging.getLogger(__name__)
_TEMPLATE_ENV = Environment(autoescape=select_autoescape(["html", "xml"]))

_REPORT_TEMPLATE = _TEMPLATE_ENV.from_string("""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{{ cover_title or (case_name ~ ' - 执行报告') }}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:32px;color:#333;background:#fff}
h1{font-size:24px;margin-bottom:12px}
h2{font-size:18px;margin:24px 0 12px}
.cover{display:flex;align-items:center;gap:16px;margin-bottom:24px;padding-bottom:16px;border-bottom:2px solid #1890ff}
.cover img{max-height:48px}
.cover .title{font-size:22px;font-weight:600;color:#1890ff}
.meta-table,.step-table{border-collapse:collapse;width:100%}
.meta-table{margin-bottom:20px}
.meta-table td,.meta-table th,.step-table td,.step-table th{border:1px solid #e8e8e8;padding:8px 12px;text-align:left;font-size:13px;vertical-align:top}
.meta-table th,.step-table th{background:#fafafa;color:#595959}
.badge{display:inline-block;padding:2px 10px;border-radius:4px;font-size:12px;font-weight:600;color:#fff}
.badge-passed{background:#52c41a}.badge-failed{background:#ff4d4f}
.badge-error{background:#fa8c16}.badge-running{background:#1890ff}
.badge-pending{background:#d9d9d9;color:#666}.badge-skipped{background:#bfbfbf;color:#666}
.error-box{background:#fff2f0;border:1px solid #ffccc7;border-radius:4px;padding:8px 12px;color:#cf1322;font-size:13px;white-space:pre-wrap;word-break:break-all}
.screenshot{max-width:100%;border:1px solid #f0f0f0;border-radius:6px;margin-top:8px}
.muted{color:#999}
.footer{margin-top:32px;padding-top:16px;border-top:1px solid #f0f0f0;color:#999;font-size:12px;text-align:center}
</style>
</head>
<body>
{% if cover_title or cover_logo_url %}
<div class="cover">
  {% if cover_logo_url %}<img src="{{ cover_logo_url }}" alt="logo">{% endif %}
  <div class="title">{{ cover_title or case_name }}</div>
</div>
{% endif %}
<h1>{{ case_name }} 执行报告 {% if template_mode == 'summary' %}<span style="font-size:13px;color:#999">(简洁版)</span>{% endif %}</h1>
{% if video_url %}
<div style="margin:16px 0 24px">
  <h2 style="margin-top:0">执行录像</h2>
  <video controls preload="metadata" style="max-width:100%;border:1px solid #f0f0f0;border-radius:6px" src="{{ video_url }}"></video>
  <p class="muted" style="margin-top:4px;font-size:12px">如视频无法播放，<a href="{{ video_url }}" target="_blank">点此直接下载</a></p>
</div>
{% endif %}
<table class="meta-table">
<tr><th>执行 ID</th><td>{{ run.id }}</td><th>状态</th><td><span class="badge badge-{{ run_status }}">{{ run_status }}</span></td></tr>
<tr><th>用例类型</th><td>{{ case_type or '-' }}</td><th>耗时</th><td>{{ '%.1fs' % ((run.duration_ms or 0) / 1000) }}</td></tr>
<tr><th>生成时间</th><td>{{ now }}</td><th>错误信息</th><td>{% if run.error_message %}<span class="error-box">{{ run.error_message }}</span>{% else %}<span class="muted">-</span>{% endif %}</td></tr>
</table>
<h2>步骤明细</h2>
{% if steps %}
<table class="step-table">
<thead><tr><th>序号</th><th>步骤</th><th>状态</th><th>耗时</th>{% if template_mode != 'summary' %}<th>错误信息</th><th>截图</th>{% endif %}</tr></thead>
<tbody>
{% for step in steps %}
<tr>
<td>{{ step.step_index }}</td>
<td>{{ step.name or '-' }}</td>
<td><span class="badge badge-{{ step.status }}">{{ step.status }}</span></td>
<td>{{ '%.1fs' % ((step.duration_ms or 0) / 1000) }}</td>
{% if template_mode != 'summary' %}
<td>{% if step.error_message %}<span class="error-box">{{ step.error_message }}</span>{% else %}<span class="muted">-</span>{% endif %}</td>
<td>{% if step.screenshot_b64 %}<img class="screenshot" src="data:image/png;base64,{{ step.screenshot_b64 }}" alt="step screenshot" />{% else %}<span class="muted">-</span>{% endif %}</td>
{% endif %}
</tr>
{% endfor %}
</tbody>
</table>
{% else %}
<p class="muted">暂无步骤明细</p>
{% endif %}
<div class="footer">ATP 自动化测试平台 &mdash; 报告生成于 {{ now }}</div>
</body>
</html>
""")

_AGGREGATE_REPORT_TEMPLATE = _TEMPLATE_ENV.from_string("""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{{ title }}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:32px;color:#333;background:#fff}
h1{font-size:24px;margin-bottom:12px}
h2{font-size:18px;margin:24px 0 12px}
h3{font-size:15px;margin:0}
.meta-table{border-collapse:collapse;width:100%;margin-bottom:20px}
.meta-table td,.meta-table th{border:1px solid #e8e8e8;padding:8px 12px;text-align:left;font-size:13px}
.meta-table th{background:#fafafa;width:140px;color:#595959}
.badge{display:inline-block;padding:2px 10px;border-radius:4px;font-size:12px;font-weight:600;color:#fff}
.badge-passed{background:#52c41a}.badge-failed{background:#ff4d4f}
.badge-error{background:#fa8c16}.badge-running{background:#1890ff}
.badge-pending{background:#d9d9d9;color:#666}.badge-skipped{background:#bfbfbf;color:#666}
.summary{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.summary-card{border:1px solid #e8e8e8;border-radius:8px;padding:12px 16px;min-width:120px;background:#fafafa}
.summary-card .label{font-size:12px;color:#999;margin-bottom:4px}
.summary-card .value{font-size:22px;font-weight:600}
.section{border:1px solid #e8e8e8;border-radius:8px;margin-bottom:16px;overflow:hidden}
.section-header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#fafafa;border-bottom:1px solid #f0f0f0}
.section-body{padding:16px}
.data-table{border-collapse:collapse;width:100%}
.data-table td,.data-table th{border:1px solid #f0f0f0;padding:8px 10px;text-align:left;font-size:13px;vertical-align:top}
.data-table th{background:#fcfcfc;color:#595959}
.muted{color:#999}
.error-box{background:#fff2f0;border:1px solid #ffccc7;border-radius:4px;padding:8px 12px;color:#cf1322;font-size:13px;white-space:pre-wrap;word-break:break-all}
.footer{margin-top:32px;padding-top:16px;border-top:1px solid #f0f0f0;color:#999;font-size:12px;text-align:center}
@media print{
  body{padding:16px}
  .section{break-inside:avoid}
  .badge{print-color-adjust:exact;-webkit-print-color-adjust:exact}
}
</style>
</head>
<body>
<h1>{{ title }}</h1>
<table class="meta-table">
{% for row in meta_rows %}
<tr>
{% for cell in row %}
<th>{{ cell.label }}</th><td>{{ cell.value }}</td>
{% endfor %}
</tr>
{% endfor %}
</table>
<div class="summary">
  <div class="summary-card"><div class="label">总数</div><div class="value">{{ summary.total }}</div></div>
  <div class="summary-card"><div class="label">通过</div><div class="value">{{ summary.passed }}</div></div>
  <div class="summary-card"><div class="label">失败</div><div class="value">{{ summary.failed }}</div></div>
  <div class="summary-card"><div class="label">错误</div><div class="value">{{ summary.error }}</div></div>
</div>
{% for section in sections %}
<div class="section">
  <div class="section-header">
    <h3>{{ section.title }}</h3>
    <span><span class="badge badge-{{ section.status }}">{{ section.status }}</span>{% if section.duration %} {{ section.duration }}{% endif %}</span>
  </div>
  <div class="section-body">
    {% if section.description %}<p style="margin-bottom:12px">{{ section.description }}</p>{% endif %}
    {% if section.error_message %}<div class="error-box" style="margin-bottom:12px">{{ section.error_message }}</div>{% endif %}
    {% if section.rows %}
    <table class="data-table">
      <thead>
        <tr>
          {% for header in section.headers %}<th>{{ header }}</th>{% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for row in section.rows %}
        <tr>
          <td>{{ row.name }}</td>
          <td>{{ row.status }}</td>
          <td>{{ row.duration }}</td>
          <td>{{ row.environment }}</td>
          <td>{% if row.error_message %}<span class="error-box" style="display:block">{{ row.error_message }}</span>{% else %}<span class="muted">-</span>{% endif %}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="muted">暂无明细数据</p>
    {% endif %}
  </div>
</div>
{% endfor %}
<div class="footer">ATP 自动化测试平台 &mdash; 报告生成于 {{ now }}</div>
</body>
</html>
""")


def _extract_minio_object(url: str) -> str | None:
    """从 MinIO presigned URL 或对象路径中提取 object name"""
    return extract_object_name(url)


def _build_report_steps_view(steps: list[StepResult]) -> list[dict]:
    rendered_steps: list[dict] = []
    for step in steps:
        screenshot_b64 = ""
        if step.screenshot_url:
            obj_name = _extract_minio_object(step.screenshot_url)
            if obj_name:
                try:
                    img_bytes = read_bytes(obj_name)
                    screenshot_b64 = base64.b64encode(img_bytes).decode()
                except Exception:
                    logger.warning(f"Failed to read screenshot: {obj_name}")
        rendered_steps.append(
            {
                "step_index": step.step_index,
                "name": step.name,
                "status": getattr(step.status, "value", step.status),
                "duration_ms": step.duration_ms,
                "error_message": step.error_message,
                "screenshot_b64": screenshot_b64,
            }
        )
    return rendered_steps


async def _build_report_html(
    run: TestRun,
    steps: list[StepResult],
    case_name: str,
    case_type: str = "",
    template_mode: str = "full",
    cover_title: str | None = None,
    cover_logo_url: str | None = None,
    include_video: bool = True,
) -> str:
    """构建 HTML 报告，截图内嵌为 base64。

    template_mode: "full"（默认，含错误信息+截图）/ "summary"（仅步骤名+状态+耗时）
    cover_title / cover_logo_url: 自定义封面标题与 Logo（E.1）
    include_video: 若 run.result_summary.video_url 存在则嵌入 <video>（P1.1）；
                   PDF 渲染路径应传 False（PDF 不支持视频）。
    """
    run_status = getattr(run.status, "value", str(run.status))
    tz_cst = timezone(timedelta(hours=8))
    rendered_steps = (
        _build_report_steps_view(steps)
        if template_mode == "full"
        else [
            {
                "step_index": s.step_index,
                "name": s.name,
                "status": getattr(s.status, "value", s.status),
                "duration_ms": s.duration_ms,
                "error_message": None,
                "screenshot_b64": "",
            }
            for s in steps
        ]
    )
    video_url = None
    if include_video:
        summary = getattr(run, "result_summary", None) or {}
        if isinstance(summary, dict):
            candidate = summary.get("video_url")
            if isinstance(candidate, str) and candidate:
                video_url = candidate
    html = _REPORT_TEMPLATE.render(
        run=run,
        run_status=run_status,
        steps=rendered_steps,
        case_name=case_name,
        case_type=case_type,
        template_mode=template_mode,
        cover_title=cover_title,
        cover_logo_url=cover_logo_url,
        video_url=video_url,
        now=datetime.now(tz_cst).strftime("%Y-%m-%d %H:%M:%S (UTC+8)"),
    )
    return html


def _report_cache_object_name(run: TestRun, template_mode: str, cover_signature: str) -> str:
    """构造 MinIO 缓存 key。包含 updated_at（毫秒）+ template + cover hash，保证内容变化即失效。"""
    ts = ""
    if run.updated_at:
        ts = run.updated_at.strftime("%Y%m%d%H%M%S%f")
    suffix = hashlib.md5(
        f"{template_mode}|{cover_signature}|{ts}".encode(),
        usedforsecurity=False,
    ).hexdigest()[:12]
    return f"reports/run-{run.id}/{template_mode}-{suffix}.html"


def _try_read_cached_report(object_name: str) -> bytes | None:
    try:
        return read_bytes(object_name)
    except Exception:
        return None


def _try_write_cached_report(object_name: str, html: str) -> None:
    try:
        from app.core.minio_client import upload_bytes

        upload_bytes(object_name, html.encode("utf-8"), content_type="text/html; charset=utf-8")
    except Exception as exc:
        logger.warning(f"report cache write skipped: {exc}")


async def _render_pdf_from_html(html: str) -> bytes:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={
                "top": "20mm",
                "bottom": "20mm",
                "left": "15mm",
                "right": "15mm",
            },
        )
        await browser.close()
    return pdf_bytes


def _normalize_status(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value or "pending")


def _format_duration(duration_ms: object) -> str:
    if duration_ms is None:
        return "-"
    try:
        return f"{int(duration_ms) / 1000:.1f}s"
    except Exception:
        return "-"


def _merge_summary(summary: dict | None, total: int) -> dict[str, int]:
    data = dict(summary or {})
    return {
        "total": int(data.get("total", total) or total),
        "passed": int(data.get("passed", 0) or 0),
        "failed": int(data.get("failed", 0) or 0),
        "error": int(data.get("error", 0) or 0),
    }


async def _build_suite_run_report_html(db: AsyncSession, suite_run: SuiteRun) -> str:
    from datetime import datetime, timezone, timedelta

    case_rows = []
    for item in suite_run.case_run_ids or []:
        case_run_id = item.get("run_id")
        actual_run = await db.get(TestRun, case_run_id) if case_run_id else None
        case_rows.append(
            {
                "name": item.get("case_name", f"Case-{item.get('case_id', '?')}"),
                "status": item.get("status", _normalize_status(getattr(actual_run, "status", None))),
                "duration": _format_duration(item.get("duration_ms") or getattr(actual_run, "duration_ms", None)),
                "environment": getattr(actual_run, "environment", None) or "-",
                "error_message": item.get("error") or getattr(actual_run, "error_message", None) or "",
            }
        )

    summary = _merge_summary(suite_run.result_summary, len(case_rows))
    tz_cst = timezone(timedelta(hours=8))
    return _AGGREGATE_REPORT_TEMPLATE.render(
        title=f"套件执行报告 #{suite_run.id}",
        meta_rows=[
            [{"label": "套件执行 ID", "value": suite_run.id}, {"label": "套件 ID", "value": suite_run.suite_id}],
            [
                {"label": "状态", "value": _normalize_status(suite_run.status)},
                {"label": "耗时", "value": _format_duration(suite_run.duration_ms)},
            ],
            [
                {
                    "label": "触发时间",
                    "value": suite_run.created_at.strftime("%Y-%m-%d %H:%M:%S") if suite_run.created_at else "-",
                },
                {"label": "备注", "value": "按用例执行结果聚合"},
            ],
        ],
        summary=summary,
        sections=[
            {
                "title": "用例执行明细",
                "status": _normalize_status(suite_run.status),
                "duration": _format_duration(suite_run.duration_ms),
                "description": "当前套件下所有用例执行结果。",
                "error_message": suite_run.error_message,
                "headers": ["用例", "状态", "耗时", "环境", "错误信息"],
                "rows": case_rows,
            }
        ],
        now=datetime.now(tz_cst).strftime("%Y-%m-%d %H:%M:%S (UTC+8)"),
    )


async def _build_plan_run_report_html(db: AsyncSession, plan_run: PlanRun) -> str:
    from datetime import datetime, timezone, timedelta

    sections = []
    total_cases = 0
    passed = 0
    failed = 0
    error = 0

    for item in plan_run.suite_run_ids or []:
        suite_run_id = item.get("suite_run_id")
        suite_run = await db.get(SuiteRun, suite_run_id) if suite_run_id else None
        case_rows = []
        suite_summary = _merge_summary(
            getattr(suite_run, "result_summary", None), len(getattr(suite_run, "case_run_ids", []) or [])
        )
        total_cases += suite_summary["total"]
        passed += suite_summary["passed"]
        failed += suite_summary["failed"]
        error += suite_summary["error"]

        for case_item in getattr(suite_run, "case_run_ids", []) or []:
            case_run_id = case_item.get("run_id")
            actual_run = await db.get(TestRun, case_run_id) if case_run_id else None
            case_rows.append(
                {
                    "name": case_item.get("case_name", f"Case-{case_item.get('case_id', '?')}"),
                    "status": case_item.get("status", _normalize_status(getattr(actual_run, "status", None))),
                    "duration": _format_duration(
                        case_item.get("duration_ms") or getattr(actual_run, "duration_ms", None)
                    ),
                    "environment": getattr(actual_run, "environment", None) or "-",
                    "error_message": case_item.get("error") or getattr(actual_run, "error_message", None) or "",
                }
            )

        sections.append(
            {
                "title": item.get("suite_name", f"Suite-{item.get('suite_id', '?')}"),
                "status": _normalize_status(getattr(suite_run, "status", item.get("status", "pending"))),
                "duration": _format_duration(getattr(suite_run, "duration_ms", None)),
                "description": f"套件执行 ID：{suite_run_id or '-'}",
                "error_message": item.get("error") or getattr(suite_run, "error_message", None),
                "headers": ["用例", "状态", "耗时", "环境", "错误信息"],
                "rows": case_rows,
            }
        )

    summary = {"total": total_cases, "passed": passed, "failed": failed, "error": error}
    tz_cst = timezone(timedelta(hours=8))
    return _AGGREGATE_REPORT_TEMPLATE.render(
        title=f"计划执行报告 #{plan_run.id}",
        meta_rows=[
            [{"label": "计划执行 ID", "value": plan_run.id}, {"label": "计划 ID", "value": plan_run.plan_id}],
            [
                {"label": "状态", "value": _normalize_status(plan_run.status)},
                {"label": "耗时", "value": _format_duration(plan_run.duration_ms)},
            ],
            [
                {
                    "label": "触发时间",
                    "value": plan_run.created_at.strftime("%Y-%m-%d %H:%M:%S") if plan_run.created_at else "-",
                },
                {"label": "备注", "value": "按套件与用例结果聚合"},
            ],
        ],
        summary=summary,
        sections=sections,
        now=datetime.now(tz_cst).strftime("%Y-%m-%d %H:%M:%S (UTC+8)"),
    )


@router.get("/runs/{run_id}/export/html")
async def export_run_html(
    run_id: int,
    template: str = Query("full", pattern="^(full|summary)$"),
    cover_title: str | None = Query(None, max_length=200),
    cover_logo_url: str | None = Query(None, max_length=500),
    use_cache: bool = Query(True, description="命中 MinIO 缓存则直接返回"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """导出执行报告为 HTML（截图内嵌 base64）。

    E.1: template=summary 不渲染请求/响应/截图；cover_title/cover_logo_url 自定义封面；
    use_cache=True 时命中 MinIO 缓存直接返回，缓存 key 含 updated_at 自动失效。
    """
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    cover_sig = f"{cover_title or ''}|{cover_logo_url or ''}"
    cache_obj = _report_cache_object_name(run, template, cover_sig)
    if use_cache:
        cached = _try_read_cached_report(cache_obj)
        if cached:
            return Response(
                content=cached,
                media_type="text/html; charset=utf-8",
                headers={
                    "Content-Disposition": f"attachment; filename=run-{run_id}-report.html",
                    "X-Atp-Cache": "hit",
                },
            )

    result = await db.execute(select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.step_index))
    steps = result.scalars().all()

    case = await db.get(TestCase, run.case_id)
    case_name = case.name if case else f"Case-{run.case_id}"
    case_type = case.case_type.value if case else ""

    html = await _build_report_html(
        run,
        list(steps),
        case_name,
        case_type,
        template_mode=template,
        cover_title=cover_title,
        cover_logo_url=cover_logo_url,
    )
    _try_write_cached_report(cache_obj, html)
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=run-{run_id}-report.html",
            "X-Atp-Cache": "miss",
        },
    )


@router.get("/runs/{run_id}/export/pdf")
async def export_run_pdf(
    run_id: int,
    template: str = Query("full", pattern="^(full|summary)$"),
    cover_title: str | None = Query(None, max_length=200),
    cover_logo_url: str | None = Query(None, max_length=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """导出执行报告为 PDF（通过 Playwright 渲染 HTML）"""
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    result = await db.execute(select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.step_index))
    steps = result.scalars().all()

    case = await db.get(TestCase, run.case_id)
    case_name = case.name if case else f"Case-{run.case_id}"
    case_type = case.case_type.value if case else ""

    html = await _build_report_html(
        run,
        list(steps),
        case_name,
        case_type,
        template_mode=template,
        cover_title=cover_title,
        cover_logo_url=cover_logo_url,
        include_video=False,
    )
    pdf_bytes = await _render_pdf_from_html(html)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=run-{run_id}-report.pdf"},
    )


@router.post("/runs/export/zip")
async def export_runs_zip(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """批量导出多个执行记录的 HTML 报告为 ZIP（E.1）。

    body: {"run_ids": [int], "template": "full"|"summary", "cover_title": str?, "cover_logo_url": str?}
    最多 50 个 run_id；逐个生成 HTML 后打包，缺失的 run 跳过并在 _missing.txt 中记录。
    """
    run_ids = payload.get("run_ids") or []
    if not isinstance(run_ids, list) or not run_ids:
        raise HTTPException(status_code=400, detail="run_ids 不能为空")
    if len(run_ids) > 50:
        raise HTTPException(status_code=400, detail="单次最多导出 50 条")

    template_mode = payload.get("template", "full")
    if template_mode not in ("full", "summary"):
        raise HTTPException(status_code=400, detail="template 仅支持 full|summary")
    cover_title = payload.get("cover_title")
    cover_logo_url = payload.get("cover_logo_url")

    buf = io.BytesIO()
    missing: list[int] = []
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rid in run_ids:
            try:
                rid_int = int(rid)
            except (TypeError, ValueError):
                missing.append(rid)
                continue
            run = await db.get(TestRun, rid_int)
            if not run:
                missing.append(rid_int)
                continue
            result = await db.execute(
                select(StepResult).where(StepResult.run_id == rid_int).order_by(StepResult.step_index)
            )
            steps = result.scalars().all()
            case = await db.get(TestCase, run.case_id)
            case_name = case.name if case else f"Case-{run.case_id}"
            case_type = case.case_type.value if case else ""
            html = await _build_report_html(
                run,
                list(steps),
                case_name,
                case_type,
                template_mode=template_mode,
                cover_title=cover_title,
                cover_logo_url=cover_logo_url,
            )
            zf.writestr(f"run-{rid_int}-report.html", html)
        if missing:
            zf.writestr(
                "_missing.txt",
                "以下 run_id 未找到或无效：\n" + "\n".join(str(m) for m in missing),
            )

    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=runs-bundle.zip"},
    )


@router.get("/suite-runs/{run_id}/export/html")
async def export_suite_run_html(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    suite_run = await db.get(SuiteRun, run_id)
    if not suite_run:
        raise HTTPException(status_code=404, detail="套件执行记录不存在")

    html = await _build_suite_run_report_html(db, suite_run)
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=suite-run-{run_id}-report.html"},
    )


@router.get("/suite-runs/{run_id}/export/pdf")
async def export_suite_run_pdf(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    suite_run = await db.get(SuiteRun, run_id)
    if not suite_run:
        raise HTTPException(status_code=404, detail="套件执行记录不存在")

    html = await _build_suite_run_report_html(db, suite_run)
    pdf_bytes = await _render_pdf_from_html(html)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=suite-run-{run_id}-report.pdf"},
    )


@router.get("/plan-runs/{run_id}/export/html")
async def export_plan_run_html(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan_run = await db.get(PlanRun, run_id)
    if not plan_run:
        raise HTTPException(status_code=404, detail="计划执行记录不存在")

    html = await _build_plan_run_report_html(db, plan_run)
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=plan-run-{run_id}-report.html"},
    )


@router.get("/plan-runs/{run_id}/export/pdf")
async def export_plan_run_pdf(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan_run = await db.get(PlanRun, run_id)
    if not plan_run:
        raise HTTPException(status_code=404, detail="计划执行记录不存在")

    html = await _build_plan_run_report_html(db, plan_run)
    pdf_bytes = await _render_pdf_from_html(html)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=plan-run-{run_id}-report.pdf"},
    )
