"""接口契约与业务 Spec 驱动的端到端用例智能生成编排器 (T3.1)。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class EndpointContractSpec:
    """单个接口契约元数据定义。"""

    path: str
    method: str = "POST"
    summary: str = ""
    request_schema: dict[str, Any] = field(default_factory=dict)
    response_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class SynthesizedStepItem:
    """端到端用例中的单个时序执行步骤。"""

    step_index: int
    step_name: str
    endpoint: str
    method: str
    request_payload: dict[str, Any]
    extracted_variables: dict[str, str]  # 导出变量: { "CURRENT_TOKEN": "$.data.token", "ORDER_ID": "$.data.order_id" }
    assertions: list[
        dict[str, Any]
    ]  # 断言列表: [ { "type": "status_code", "expected": 200 }, { "type": "jsonpath", "path": "$.code", "expected": 0 } ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "step_name": self.step_name,
            "endpoint": self.endpoint,
            "method": self.method,
            "request_payload": self.request_payload,
            "extracted_variables": self.extracted_variables,
            "assertions": self.assertions,
        }


@dataclass
class SynthesizedE2ETestCase:
    """生成的端到端业务测试用例对象。"""

    case_id: str
    spec_title: str
    description: str
    steps_count: int
    steps: list[SynthesizedStepItem]
    generated_python_script: str
    flow_completeness_score_pct: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "spec_title": self.spec_title,
            "description": self.description,
            "steps_count": self.steps_count,
            "steps": [s.to_dict() for s in self.steps],
            "generated_python_script": self.generated_python_script,
            "flow_completeness_score_pct": round(self.flow_completeness_score_pct, 1),
            "created_at": self.created_at.isoformat(),
        }


# 全局用例生成存储仓库
_SYNTHESIZED_CASES: dict[str, SynthesizedE2ETestCase] = {}


def clear_synthesized_cases_store() -> None:
    """清空用例生成仓库（单测专用）。"""
    _SYNTHESIZED_CASES.clear()


def _infer_variable_dependencies(
    endpoints: list[EndpointContractSpec],
) -> list[SynthesizedStepItem]:
    """推导各接口之间的时序与参数上下文依赖图，生成步骤链。"""
    steps: list[SynthesizedStepItem] = []
    available_context_vars: dict[str, str] = {}  # var_name -> context source

    for idx, ep in enumerate(endpoints, start=1):
        step_name = ep.summary or f"执行接口 [{ep.method} {ep.path}]"
        payload: dict[str, Any] = {}
        extracted: dict[str, str] = {}
        assertions: list[dict[str, Any]] = [
            {"type": "status_code", "expected": 200},
            {"type": "jsonpath", "path": "$.code", "expected": 0},
        ]

        # 智能匹配与填充请求入参
        req_props = ep.request_schema.get("properties", {})
        for prop_name, prop_spec in req_props.items():
            prop_type = prop_spec.get("type", "string") if isinstance(prop_spec, dict) else "string"

            # 匹配上游上下文导出的变量
            matched_var = None
            for var_key in available_context_vars:
                # 模糊匹配: token, user_id, order_id, account_id
                if prop_name.lower() in var_key.lower() or var_key.lower() in prop_name.lower():
                    matched_var = var_key
                    break

            if matched_var:
                payload[prop_name] = f"${{{matched_var}}}"
            else:
                # 默认模拟值
                if "id" in prop_name.lower():
                    payload[prop_name] = "10001" if prop_type == "integer" else "id_10001"
                elif "name" in prop_name.lower() or "username" in prop_name.lower():
                    payload[prop_name] = "test_user_alpha"
                elif "amount" in prop_name.lower() or "price" in prop_name.lower():
                    payload[prop_name] = 99.9
                elif prop_type == "integer":
                    payload[prop_name] = 1
                elif prop_type == "boolean":
                    payload[prop_name] = True
                else:
                    payload[prop_name] = f"sample_{prop_name}"

        # 智能分析响应体提取供下游使用的变量
        res_props = ep.response_schema.get("properties", {})
        data_props = res_props.get("data", {}).get("properties", {}) if isinstance(res_props.get("data"), dict) else {}
        target_dict = data_props or res_props

        for res_key in target_dict:
            res_lower = res_key.lower()
            if any(k in res_lower for k in ["token", "id", "order", "user", "ticket", "code", "tx"]):
                var_name = f"{ep.path.split('/')[-1].upper()}_{res_key.upper()}"
                var_name = re.sub(r"[^A-Z0-9_]", "", var_name)
                json_path = f"$.data.{res_key}" if data_props else f"$.{res_key}"
                extracted[var_name] = json_path
                available_context_vars[var_name] = json_path

        steps.append(
            SynthesizedStepItem(
                step_index=idx,
                step_name=step_name,
                endpoint=ep.path,
                method=ep.method.upper(),
                request_payload=payload,
                extracted_variables=extracted,
                assertions=assertions,
            )
        )

    return steps


def _render_python_e2e_script(spec_title: str, steps: list[SynthesizedStepItem]) -> str:
    """将步骤列表组装渲染为标准独立的 pytest + httpx Python 脚本。"""
    code_lines = [
        '"""ATP 自动合成端到端业务集成测试用例脚本。"""',
        "",
        "import pytest",
        "import httpx",
        "",
        "@pytest.mark.asyncio",
        f"async def test_e2e_{re.sub(r'[^a-zA-Z0-9_]', '_', spec_title.lower()).strip('_')}():",
        '    """业务场景: ' + spec_title + '"""',
        "    context_vars = {}",
        '    async with httpx.AsyncClient(base_url="https://api.test-env.internal", timeout=10.0) as client:',
    ]

    for step in steps:
        code_lines.append(f"        # Step {step.step_index}: {step.step_name}")
        code_lines.append(f"        # 请求目标: {step.method} {step.endpoint}")
        code_lines.append(f"        step_{step.step_index}_payload = {step.request_payload}")
        code_lines.append("        # 替换上游时序导出的动态上下文变量")
        code_lines.append(f"        for k, v in step_{step.step_index}_payload.items():")
        code_lines.append("            if isinstance(v, str) and v.startswith('${') and v.endswith('}'):")
        code_lines.append("                var_key = v[2:-1]")
        code_lines.append("                if var_key in context_vars:")
        code_lines.append(f"                    step_{step.step_index}_payload[k] = context_vars[var_key]")
        code_lines.append("")
        if step.method == "POST":
            code_lines.append(
                f'        resp_{step.step_index} = await client.post("{step.endpoint}", json=step_{step.step_index}_payload)'
            )
        elif step.method == "GET":
            code_lines.append(
                f'        resp_{step.step_index} = await client.get("{step.endpoint}", params=step_{step.step_index}_payload)'
            )
        else:
            code_lines.append(
                f'        resp_{step.step_index} = await client.request("{step.method}", "{step.endpoint}", json=step_{step.step_index}_payload)'
            )

        code_lines.append(
            f"        assert resp_{step.step_index}.status_code == 200, f'Step {step.step_index} HTTP 状态码异常'"
        )
        code_lines.append(f"        res_{step.step_index}_json = resp_{step.step_index}.json()")
        code_lines.append(
            f"        assert res_{step.step_index}_json.get('code') == 0, f'Step {step.step_index} 业务状态码失败'"
        )

        # 导出变量提取
        for var_name, jsonpath in step.extracted_variables.items():
            key_name = jsonpath.split(".")[-1]
            code_lines.append(f"        # 提取下游依赖变量: {var_name}")
            if "data." in jsonpath:
                code_lines.append(
                    f"        context_vars['{var_name}'] = res_{step.step_index}_json.get('data', {{}}).get('{key_name}')"
                )
            else:
                code_lines.append(f"        context_vars['{var_name}'] = res_{step.step_index}_json.get('{key_name}')")
        code_lines.append("")

    return "\n".join(code_lines)


def synthesize_e2e_test_flow(
    spec_title: str,
    business_flow_description: str = "",
    endpoints: list[dict[str, Any]] | None = None,
) -> SynthesizedE2ETestCase:
    """根据业务流描述与 OpenAPI 契约列表合成端到端测试用例流。"""
    parsed_endpoints: list[EndpointContractSpec] = []
    if endpoints:
        for ep in endpoints:
            parsed_endpoints.append(
                EndpointContractSpec(
                    path=ep.get("path", "/api/v1/sample"),
                    method=ep.get("method", "POST").upper(),
                    summary=ep.get("summary", ""),
                    request_schema=ep.get("request_schema", {}),
                    response_schema=ep.get("response_schema", {}),
                )
            )
    else:
        # 默认生成 3 步典型标准业务闭环 (用户登录 -> 创建订单 -> 支付结算)
        parsed_endpoints = [
            EndpointContractSpec(
                path="/api/v1/auth/login",
                method="POST",
                summary="用户认证登录获取凭据",
                request_schema={"properties": {"username": {"type": "string"}, "password": {"type": "string"}}},
                response_schema={
                    "properties": {
                        "data": {"properties": {"token": {"type": "string"}, "user_id": {"type": "integer"}}}
                    }
                },
            ),
            EndpointContractSpec(
                path="/api/v1/orders/create",
                method="POST",
                summary="创建业务交易订单",
                request_schema={
                    "properties": {
                        "user_id": {"type": "integer"},
                        "amount": {"type": "number"},
                        "sku": {"type": "string"},
                    }
                },
                response_schema={
                    "properties": {
                        "data": {"properties": {"order_id": {"type": "string"}, "status": {"type": "string"}}}
                    }
                },
            ),
            EndpointContractSpec(
                path="/api/v1/payments/checkout",
                method="POST",
                summary="订单支付收银确认",
                request_schema={"properties": {"order_id": {"type": "string"}, "pay_channel": {"type": "string"}}},
                response_schema={
                    "properties": {
                        "data": {"properties": {"tx_id": {"type": "string"}, "is_success": {"type": "boolean"}}}
                    }
                },
            ),
        ]

    steps = _infer_variable_dependencies(parsed_endpoints)
    python_script = _render_python_e2e_script(spec_title=spec_title, steps=steps)

    # 完整度评估：步骤数 >= 2 且有上下文变量传递判定为高质量完整链路
    has_var_dependency = any(len(s.extracted_variables) > 0 for s in steps[:-1])
    score = 95.0 if has_var_dependency and len(steps) >= 2 else (80.0 if len(steps) >= 1 else 50.0)

    now = datetime.now(timezone.utc)
    case_id = f"e2e_{re.sub(r'[^a-zA-Z0-9_]', '_', spec_title.lower()).strip('_')[:20]}_{int(now.timestamp())}"
    test_case = SynthesizedE2ETestCase(
        case_id=case_id,
        spec_title=spec_title,
        description=business_flow_description or f"端到端业务流程: {spec_title}",
        steps_count=len(steps),
        steps=steps,
        generated_python_script=python_script,
        flow_completeness_score_pct=score,
        created_at=now,
    )
    _SYNTHESIZED_CASES[case_id] = test_case
    return test_case


def get_synthesized_case(case_id: str) -> SynthesizedE2ETestCase | None:
    """按 ID 查询生成的端到端用例。"""
    return _SYNTHESIZED_CASES.get(case_id)


def list_synthesized_cases(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史生成的端到端用例列表。"""
    cases = list(reversed(list(_SYNTHESIZED_CASES.values())))
    return [c.to_dict() for c in cases[:limit]]
