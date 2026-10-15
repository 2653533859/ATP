"""Traffic Recording Session to TestCase and TestSuite Converter Service (T1.3).

Provides:
1. Automated transformation of recorded, cleaned, and parameterized traffic entries into TestCase assets.
2. Intelligent assertion generation (HTTP status codes, business code/success JSONPaths, duration thresholds).
3. TestCase and CaseStep schema creation and optional database persistence.
4. Multi-step test suite (TestSuite) composition from complex recorded user journeys.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseStatus, CaseType, TestCase, CaseStep
from app.models.suite import SuiteStatus, TestSuite
from app.schemas.case import CaseLevel, CasePriority, CaseStepCreate, TestCaseCreate
from app.services.dynamic_param_extractor import extract_and_parameterize_traffic_stream
from app.services.traffic_recorder_gateway import get_recording_session

logger = logging.getLogger(__name__)


def generate_step_assertions(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Automatically generate robust verification assertions for an API traffic step."""
    status_code = int(entry.get("status_code", 200))
    duration_ms = float(entry.get("duration_ms", 100.0))
    resp_body = entry.get("response_body")

    assertions: list[dict[str, Any]] = [
        # 1. HTTP Status Code assertion
        {
            "target": "status_code",
            "operator": "eq",
            "expected": status_code,
            "description": f"验证 HTTP 响应状态码为 {status_code}",
        },
    ]

    # 2. Response body JSONPath business code/status assertions
    if isinstance(resp_body, dict):
        if "code" in resp_body:
            assertions.append(
                {
                    "target": "body",
                    "type": "jsonpath",
                    "expression": "$.code",
                    "operator": "eq",
                    "expected": resp_body["code"],
                    "description": f"验证业务响应码 code == {resp_body['code']}",
                }
            )
        if "success" in resp_body and isinstance(resp_body["success"], bool):
            assertions.append(
                {
                    "target": "body",
                    "type": "jsonpath",
                    "expression": "$.success",
                    "operator": "eq",
                    "expected": resp_body["success"],
                    "description": f"验证接口调用成功标志 success == {resp_body['success']}",
                }
            )
        if "status" in resp_body and isinstance(resp_body["status"], (str, int)):
            assertions.append(
                {
                    "target": "body",
                    "type": "jsonpath",
                    "expression": "$.status",
                    "operator": "eq",
                    "expected": resp_body["status"],
                    "description": f"验证业务状态 status == {resp_body['status']}",
                }
            )

    # 3. Latency SLA upper-bound assertion (at least 3x baseline or 3000ms max)
    max_duration = max(3000, int(duration_ms * 3.5))
    assertions.append(
        {
            "target": "duration",
            "operator": "lt",
            "expected": max_duration,
            "description": f"接口响应耗时不得超过 SLA 上限 ({max_duration}ms)",
        }
    )

    return assertions


def convert_traffic_entry_to_step(
    entry: dict[str, Any],
    step_no: int,
) -> tuple[CaseStepCreate, dict[str, Any]]:
    """Convert a recorded traffic entry into a CaseStepCreate and execution step config."""
    method = str(entry.get("method", "GET")).upper()
    path = str(entry.get("path", "/"))
    url = str(entry.get("url", path))
    status_code = int(entry.get("status_code", 200))
    req_body = entry.get("request_body")
    extractions = entry.get("extractions", [])

    step_name = f"{method} {path}"
    test_data = json.dumps(req_body, ensure_ascii=False) if req_body is not None else None
    expected_result = f"返回 HTTP {status_code} 响应成功"
    is_key_step = method != "GET" or bool(extractions)

    case_step = CaseStepCreate(
        step_no=step_no,
        action=step_name,
        test_data=test_data,
        expected_result=expected_result,
        is_key_step=is_key_step,
        remarks=f"从反向代理流量录制自动逆向合成 (耗时: {entry.get('duration_ms', 0)}ms)",
    )

    body_type = "json" if isinstance(req_body, (dict, list)) else "none"

    exec_step = {
        "step_no": step_no,
        "name": step_name,
        "url": url,
        "method": method,
        "headers": entry.get("headers", {}),
        "params": entry.get("query_params", {}),
        "body": req_body,
        "body_type": body_type,
        "timeout": 30,
        "extractions": extractions,
        "assertions": generate_step_assertions(entry),
    }

    return case_step, exec_step


async def synthesize_case_from_traffic(
    raw_entries: list[dict[str, Any]],
    *,
    case_name: str,
    module_id: int,
    owner_id: int,
    project_id: int,
    description: str | None = None,
    priority: CasePriority = "P1",
    case_level: CaseLevel = "core",
    persist: bool = False,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Synthesize clean parameterized traffic entries into a unified multi-step TestCase."""
    # 1. Parameterize dependencies
    param_res = extract_and_parameterize_traffic_stream(raw_entries)
    param_entries = param_res["parameterized_entries"]
    clean_entries = [e for e in param_entries if not e.get("is_noise")]

    if not clean_entries:
        raise ValueError("传入的录制流量中没有有效的业务请求（全部为静态资源或探针心跳）")

    case_steps: list[CaseStepCreate] = []
    exec_steps: list[dict[str, Any]] = []

    for idx, entry in enumerate(clean_entries, start=1):
        c_step, e_step = convert_traffic_entry_to_step(entry, idx)
        case_steps.append(c_step)
        exec_steps.append(e_step)

    test_case_payload = TestCaseCreate(
        name=case_name,
        description=description or "从微服务反向代理流量自动逆向合成的业务场景测试用例",
        case_type=CaseType.api,
        module_id=module_id,
        priority=priority,
        case_level=case_level,
        owner_id=owner_id,
        steps=case_steps,
        config={"steps": exec_steps},
    )

    persisted_case_id: int | None = None

    if persist:
        if db is None:
            raise ValueError("持久化落库需要传入有效的数据库会话 (db)")
        test_case = TestCase(
            name=test_case_payload.name,
            description=test_case_payload.description,
            case_type=CaseType.api,
            module_id=module_id,
            priority=priority,
            case_level=case_level,
            owner_id=owner_id,
            config=test_case_payload.config,
            status=CaseStatus.active,
        )
        db.add(test_case)
        await db.flush()

        for st in case_steps:
            db_step = CaseStep(
                case_id=test_case.id,
                step_no=st.step_no or 1,
                action=st.action,
                test_data=st.test_data,
                expected_result=st.expected_result,
                is_key_step=st.is_key_step,
                remarks=st.remarks,
            )
            db.add(db_step)

        await db.commit()
        await db.refresh(test_case)
        persisted_case_id = test_case.id

    return {
        "case_id": persisted_case_id,
        "name": case_name,
        "module_id": module_id,
        "project_id": project_id,
        "total_steps": len(case_steps),
        "steps": [s.model_dump() for s in case_steps],
        "config": test_case_payload.config,
        "dependencies_extracted": param_res["discovered_dependencies"],
        "persisted": persist,
    }


async def synthesize_suite_from_session(
    session_id: str,
    *,
    suite_name: str,
    module_id: int,
    project_id: int,
    owner_id: int,
    persist: bool = False,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Convert an entire recorded session into a synthesized TestCase and wrap it in a TestSuite."""
    session = get_recording_session(session_id)
    if not session:
        raise ValueError(f"未找到录制会话: '{session_id}'")

    raw_entries = [e.to_dict() for e in session.entries]
    case_res = await synthesize_case_from_traffic(
        raw_entries,
        case_name=f"{suite_name} - 主流程用例",
        module_id=module_id,
        owner_id=owner_id,
        project_id=project_id,
        persist=persist,
        db=db,
    )

    persisted_suite_id: int | None = None

    if persist and case_res["case_id"] and db is not None:
        suite = TestSuite(
            name=suite_name,
            project_id=project_id,
            creator_id=owner_id,
            status=SuiteStatus.active,
            case_ids=[{"case_id": case_res["case_id"], "sort": 0}],
            config={"execution_mode": "sequential"},
        )
        db.add(suite)
        await db.commit()
        await db.refresh(suite)
        persisted_suite_id = suite.id

    return {
        "suite_id": persisted_suite_id,
        "suite_name": suite_name,
        "project_id": project_id,
        "case_summary": case_res,
        "persisted": persist,
    }
