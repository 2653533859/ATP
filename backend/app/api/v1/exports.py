"""
导出接口

GET /runs/{id}/junit          单用例执行结果 JUnit XML
GET /suite-runs/{id}/junit    套件执行结果 JUnit XML
GET /plan-runs/{id}/junit     计划执行结果 JUnit XML
GET /runs/{id}/export/html    执行报告 HTML（内嵌截图）
GET /runs/{id}/export/pdf     执行报告 PDF
"""
import base64
import logging
import tempfile
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.minio_client import read_bytes
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

    result = await db.execute(
        select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.step_index)
    )
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
    suite_el = ET.SubElement(root, "testsuite", {
        "name": f"TestRun-{run.id}",
        "tests": str(tests_count),
        "failures": str(failures_count),
        "errors": str(errors_count),
        "time": f"{(run.duration_ms or 0) / 1000:.3f}",
    })

    if has_run_level_issue:
        tc = ET.SubElement(suite_el, "testcase", {
            "name": f"Run-{run.id}",
            "classname": f"TestRun-{run.id}",
            "time": f"{(run.duration_ms or 0) / 1000:.3f}",
        })
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
            tc = ET.SubElement(suite_el, "testcase", {
                "name": step.name or f"Step-{step.step_index}",
                "classname": f"TestRun-{run.id}",
                "time": f"{(step.duration_ms or 0) / 1000:.3f}",
            })
            if step.status.value == "failed":
                fail = ET.SubElement(tc, "failure", {"message": step.error_message or "Assertion failed"})
                fail.text = step.error_message or ""
            elif step.status.value == "error":
                err = ET.SubElement(tc, "error", {"message": step.error_message or "Error"})
                err.text = step.error_message or ""
            elif step.status.value == "skipped":
                ET.SubElement(tc, "skipped")

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(content=xml_bytes, media_type="application/xml", headers={
        "Content-Disposition": f"attachment; filename=run-{run_id}-junit.xml"
    })


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

    suite_el = ET.SubElement(root, "testsuite", {
        "name": f"SuiteRun-{suite_run.id}",
        "tests": str(summary.get("total", len(case_runs))),
        "failures": str(summary.get("failed", 0)),
        "errors": str(summary.get("error", 0)),
        "time": f"{(suite_run.duration_ms or 0) / 1000:.3f}",
    })

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

        tc = ET.SubElement(suite_el, "testcase", {
            "name": case_name,
            "classname": f"SuiteRun-{suite_run.id}",
            "time": f"{duration / 1000:.3f}",
        })
        if case_status == "failed":
            ET.SubElement(tc, "failure", {"message": item.get("error", "Failed")})
        elif case_status == "error":
            ET.SubElement(tc, "error", {"message": item.get("error", "Error")})
        elif case_status == "skipped":
            ET.SubElement(tc, "skipped")

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(content=xml_bytes, media_type="application/xml", headers={
        "Content-Disposition": f"attachment; filename=suite-run-{run_id}-junit.xml"
    })


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
            ts = ET.SubElement(root, "testsuite", {
                "name": suite_name, "tests": "1", "errors": "1", "failures": "0", "time": "0",
            })
            tc = ET.SubElement(ts, "testcase", {"name": suite_name, "classname": f"PlanRun-{run_id}"})
            ET.SubElement(tc, "error", {"message": item.get("error", "Suite not found")})
            continue

        sr = await db.get(SuiteRun, suite_run_id)
        if not sr:
            continue

        case_runs = sr.case_run_ids or []
        sr_summary = sr.result_summary or {}

        ts = ET.SubElement(root, "testsuite", {
            "name": suite_name,
            "tests": str(sr_summary.get("total", len(case_runs))),
            "failures": str(sr_summary.get("failed", 0)),
            "errors": str(sr_summary.get("error", 0)),
            "time": f"{(sr.duration_ms or 0) / 1000:.3f}",
        })

        for cr in case_runs:
            case_name = cr.get("case_name", f"Case-{cr.get('case_id', '?')}")
            case_status = cr.get("status", "error")
            duration = 0
            if cr.get("run_id"):
                actual_run = await db.get(TestRun, cr["run_id"])
                if actual_run:
                    duration = actual_run.duration_ms or 0

            tc = ET.SubElement(ts, "testcase", {
                "name": case_name,
                "classname": suite_name,
                "time": f"{duration / 1000:.3f}",
            })
            if case_status == "failed":
                ET.SubElement(tc, "failure", {"message": cr.get("error", "Failed")})
            elif case_status == "error":
                ET.SubElement(tc, "error", {"message": cr.get("error", "Error")})
            elif case_status == "skipped":
                ET.SubElement(tc, "skipped")

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(content=xml_bytes, media_type="application/xml", headers={
        "Content-Disposition": f"attachment; filename=plan-run-{run_id}-junit.xml"
    })


# ── HTML / PDF 报告导出 ─────────────────────────────────────

logger = logging.getLogger(__name__)

_REPORT_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>执行报告 #{{ run.id }}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:32px;color:#333;background:#fff}
h1{font-size:22px;margin-bottom:16px}
.meta-table{border-collapse:collapse;width:100%;margin-bottom:24px}
.meta-table td,.meta-table th{border:1px solid #e8e8e8;padding:8px 12px;text-align:left;font-size:13px}
.meta-table th{background:#fafafa;width:120px;color:#595959}
.badge{display:inline-block;padding:2px 10px;border-radius:4px;font-size:12px;font-weight:600;color:#fff}
.badge-passed{background:#52c41a}.badge-failed{background:#ff4d4f}
.badge-error{background:#fa8c16}.badge-running{background:#1890ff}
.badge-pending{background:#d9d9d9;color:#666}.badge-skipped{background:#bfbfbf;color:#666}
.progress-bar{display:flex;height:8px;border-radius:4px;overflow:hidden;margin-bottom:24px;gap:2px}
.seg{min-width:4px;border-radius:2px}
.seg-passed{background:#52c41a}.seg-failed{background:#ff4d4f}.seg-error{background:#fa8c16}
.seg-running{background:#1890ff}.seg-pending{background:#d9d9d9}.seg-skipped{background:#bfbfbf}
.step{border:1px solid #e8e8e8;border-radius:6px;margin-bottom:12px;overflow:hidden}
.step-header{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;background:#fafafa;font-weight:500;font-size:14px}
.step-body{padding:16px}
.step-failed .step-header{background:#fff2f0;border-left:3px solid #ff4d4f}
.step-error .step-header{background:#fff7e6;border-left:3px solid #fa8c16}
.error-box{background:#fff2f0;border:1px solid #ffccc7;border-radius:4px;padding:8px 12px;margin-bottom:12px;color:#cf1322;font-size:13px}
.screenshot{max-width:100%;border-radius:6px;border:1px solid #f0f0f0;margin:8px 0}
.data-section{margin-top:12px}
.data-label{font-weight:600;color:#595959;margin-bottom:4px;font-size:13px}
pre.code{background:#f5f5f5;padding:10px;border-radius:6px;overflow-x:auto;font-size:12px;max-height:300px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.row{display:flex;gap:16px}.col{flex:1}
.footer{margin-top:32px;padding-top:16px;border-top:1px solid #f0f0f0;color:#999;font-size:12px;text-align:center}
.case-type-tag{display:inline-block;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:600;color:#fff;margin-left:8px}
.case-type-api{background:#1890ff}.case-type-web{background:#722ed1}
.case-type-android{background:#52c41a}.case-type-graphql{background:#eb2f96}
.case-type-websocket{background:#faad14;color:#333}.case-type-grpc{background:#13c2c2}
@media print{
  body{padding:16px}
  .step{break-inside:avoid}
  .screenshot{max-width:80%}
  .progress-bar{print-color-adjust:exact;-webkit-print-color-adjust:exact}
  .badge,.seg,.case-type-tag{print-color-adjust:exact;-webkit-print-color-adjust:exact}
}
</style>
</head>
<body>
<h1>执行报告 #{{ run.id }}</h1>

<table class="meta-table">
<tr><th>执行 ID</th><td>{{ run.id }}</td><th>用例 ID</th><td>{{ run.case_id }}</td></tr>
<tr><th>用例名称</th><td>{{ case_name }}{% if case_type %}<span class="case-type-tag case-type-{{ case_type }}">{{ case_type | upper }}</span>{% endif %}</td><th>状态</th><td><span class="badge badge-{{ run_status }}">{{ run_status }}</span></td></tr>
<tr><th>环境</th><td>{{ run.environment or '-' }}</td><th>耗时</th><td>{{ '%d ms' % run.duration_ms if run.duration_ms is not none else '-' }}</td></tr>
<tr><th>触发时间</th><td colspan="3">{{ run.created_at.strftime('%Y-%m-%d %H:%M:%S') if run.created_at else '-' }}</td></tr>
{% if run.error_message %}<tr><th>错误信息</th><td colspan="3" style="color:#ff4d4f">{{ run.error_message }}</td></tr>{% endif %}
</table>

{% if steps %}
<div class="progress-bar">
{% for s in steps %}<div class="seg seg-{{ s.status.value }}" style="flex:{{ [s.duration_ms or 1, 1]|max }}"></div>{% endfor %}
</div>
{% endif %}

{% for step in steps %}
<div class="step {{ 'step-failed' if step.status.value == 'failed' else ('step-error' if step.status.value == 'error' else '') }}">
  <div class="step-header">
    <span>#{{ step.step_index + 1 }} {{ step.name }}</span>
    <span><span class="badge badge-{{ step.status.value }}">{{ step.status.value }}</span> {{ '%d ms' % step.duration_ms if step.duration_ms is not none else '' }}</span>
  </div>
  <div class="step-body">
    {% if step.error_message %}<div class="error-box">{{ step.error_message }}</div>{% endif %}
    {% if step._screenshot_b64 %}<div><div class="data-label">截图</div><img class="screenshot" src="data:image/png;base64,{{ step._screenshot_b64 }}"></div>{% endif %}
    <div class="row">
      <div class="col data-section"><div class="data-label">请求</div><pre class="code">{{ step.request_data | tojson(indent=2) if step.request_data else '-' }}</pre></div>
      <div class="col data-section"><div class="data-label">响应</div><pre class="code">{{ step.response_data | tojson(indent=2) if step.response_data else '-' }}</pre></div>
    </div>
  </div>
</div>
{% endfor %}

{% if not steps %}<p style="text-align:center;color:#999;padding:40px 0">暂无步骤数据</p>{% endif %}

<div class="footer">ATP 自动化测试平台 &mdash; 报告生成于 {{ now }}</div>
</body>
</html>
""")


def _extract_minio_object(url: str) -> str | None:
    """从 MinIO presigned URL 或对象路径中提取 object name"""
    if not url:
        return None
    # presigned URL 格式: http://host:port/bucket/object?X-Amz-...
    # 直接存储的 object name 格式: screenshots/runs/1/step_0.png
    if url.startswith("http"):
        from urllib.parse import urlparse, unquote
        path = urlparse(url).path  # /bucket/object/path
        parts = path.split("/", 2)  # ['', 'bucket', 'object/path']
        if len(parts) >= 3:
            return unquote(parts[2])
    return url


async def _build_report_html(run: TestRun, steps: list[StepResult], case_name: str, case_type: str = "") -> str:
    """构建 HTML 报告，截图内嵌为 base64"""
    from datetime import datetime, timezone, timedelta

    # 尝试读取截图并转为 base64
    for step in steps:
        step._screenshot_b64 = ""  # type: ignore[attr-defined]
        if step.screenshot_url:
            obj_name = _extract_minio_object(step.screenshot_url)
            if obj_name:
                try:
                    img_bytes = read_bytes(obj_name)
                    step._screenshot_b64 = base64.b64encode(img_bytes).decode()  # type: ignore[attr-defined]
                except Exception:
                    logger.warning(f"Failed to read screenshot: {obj_name}")

    run_status = getattr(run.status, "value", str(run.status))
    tz_cst = timezone(timedelta(hours=8))
    html = _REPORT_TEMPLATE.render(
        run=run,
        run_status=run_status,
        steps=steps,
        case_name=case_name,
        case_type=case_type,
        now=datetime.now(tz_cst).strftime("%Y-%m-%d %H:%M:%S (UTC+8)"),
    )
    return html


@router.get("/runs/{run_id}/export/html")
async def export_run_html(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """导出执行报告为 HTML（截图内嵌 base64）"""
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    result = await db.execute(
        select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.step_index)
    )
    steps = result.scalars().all()

    case = await db.get(TestCase, run.case_id)
    case_name = case.name if case else f"Case-{run.case_id}"
    case_type = case.case_type.value if case else ""

    html = await _build_report_html(run, list(steps), case_name, case_type)
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=run-{run_id}-report.html"},
    )


@router.get("/runs/{run_id}/export/pdf")
async def export_run_pdf(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """导出执行报告为 PDF（通过 Playwright 渲染 HTML）"""
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    result = await db.execute(
        select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.step_index)
    )
    steps = result.scalars().all()

    case = await db.get(TestCase, run.case_id)
    case_name = case.name if case else f"Case-{run.case_id}"
    case_type = case.case_type.value if case else ""

    html = await _build_report_html(run, list(steps), case_name, case_type)

    # 使用 Playwright 将 HTML 转为 PDF
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        pdf_bytes = await page.pdf(format="A4", print_background=True, margin={
            "top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm",
        })
        await browser.close()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=run-{run_id}-report.pdf"},
    )
