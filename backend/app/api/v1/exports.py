"""
JUnit XML 导出接口

GET /runs/{id}/junit          单用例执行结果 JUnit XML
GET /suite-runs/{id}/junit    套件执行结果 JUnit XML
GET /plan-runs/{id}/junit     计划执行结果 JUnit XML
"""
import xml.etree.ElementTree as ET
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.case import TestRun, StepResult
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
