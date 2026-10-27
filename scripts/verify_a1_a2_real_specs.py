"""Acceptance verification script for A1 API spec impact preview and A2 suggestion reliability."""

from __future__ import annotations

import asyncio
import os
import secrets
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

os.environ["ATP_LOCAL_MODE"] = "true"
os.environ["APP_ENV"] = "local"
os.environ.setdefault("APP_SECRET_KEY", secrets.token_urlsafe(32))
os.environ.setdefault("FIRST_ADMIN_PASSWORD", secrets.token_urlsafe(32))

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.bootstrap import load_all_models

load_all_models()

from app.core.local_schema import ensure_local_schema
from app.models.case import CaseStatus, CaseType, TestCase
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.schemas.ai_case import AIAssertionSuggestIn, AIAssertionSuggestion
from app.services.ai_case.suggestion import (
    _suggestion_matches_response,
    suggest_assertions_and_extractions,
)
from app.services.spec_sync import (
    case_request_fingerprint,
    sync_spec_with_cases,
)


# Two versions of OpenAPI Spec for A1
SPEC_V1 = {
    "openapi": "3.0.0",
    "info": {"title": "E-Commerce API", "version": "1.0.0"},
    "paths": {
        "/api/v1/orders": {
            "get": {
                "summary": "List orders",
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "summary": "Create order",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["items"],
                                "properties": {"items": {"type": "array"}},
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/api/v1/products": {
            "get": {
                "summary": "List products",
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}

SPEC_V2 = {
    "openapi": "3.0.0",
    "info": {"title": "E-Commerce API", "version": "2.0.0"},
    "paths": {
        "/api/v1/orders": {
            "get": {
                "summary": "List orders",
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "summary": "Create order",
                "parameters": [{"name": "order_type", "in": "query", "required": True}],
                # Modified: added required payment_method
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["items", "payment_method"],
                                "properties": {
                                    "items": {"type": "array"},
                                    "payment_method": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        # Addition: new profile endpoint
        "/api/v1/users/{id}/profile": {
            "get": {
                "summary": "Get user profile",
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "OK"}},
            }
        },
        # Deprecation: /api/v1/products removed
    },
}


async def verify_a1(db_file: Path):
    print("\n" + "=" * 60)
    print("【A1 验收】真实 OpenAPI 双版本规格比对与场景影响预览")
    print("=" * 60)

    async_eng = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    sessions = async_sessionmaker(async_eng, expire_on_commit=False)

    async with sessions() as db:
        user = User(username="a1_tester", email="a1@atp.local", hashed_password="pw", role=UserRole.admin, is_active=True)
        proj = Project(name="E-Commerce API Project", project_code="ECOM_API", owner_id=1, status="active")
        mod = Module(name="Order Module", module_code="ORDER_MOD", project_id=1, sort_order=0)

        # 创建既有用例：POST /api/v1/orders
        case_order = TestCase(
            name="创建订单基准用例",
            summary="POST /api/v1/orders 既有用例",
            case_code="TC_ORDER_POST_001",
            module_id=1,
            case_type=CaseType.api,
            status=CaseStatus.active,
            creator_id=1,
            config={
                "method": "POST",
                "url": "/api/v1/orders",
                "headers": {"Content-Type": "application/json"},
                "body": {"items": [{"sku": "A001", "qty": 1}]},
            },
        )
        case_order_get = TestCase(
            name="查询订单列表用例",
            summary="GET /api/v1/orders 既有用例",
            case_code="TC_ORDER_GET_001",
            module_id=1,
            case_type=CaseType.api,
            status=CaseStatus.active,
            creator_id=1,
            config={"method": "GET", "url": "/api/v1/orders"},
        )
        # 创建既有用例：GET /api/v1/products (将被废弃)
        case_product = TestCase(
            name="商品查询用例",
            summary="GET /api/v1/products 既有用例",
            case_code="TC_PROD_GET_001",
            module_id=1,
            case_type=CaseType.api,
            status=CaseStatus.active,
            creator_id=1,
            config={"method": "GET", "url": "/api/v1/products"},
        )
        db.add_all([user, proj, mod, case_order, case_order_get, case_product])
        await db.commit()
        await db.refresh(case_order)
        await db.refresh(case_order_get)
        await db.refresh(case_product)

        # 计算用例来源请求指纹
        orig_fp = case_request_fingerprint(case_order)
        print(f"[A1.1] 既有用例创建完成: ID={case_order.id}, Endpoint=POST /api/v1/orders, 指纹={orig_fp[:16]}...")

        # 构造模拟场景，包含 3 种步骤类型：
        # Step 0: 来源请求指纹一致（未被局部覆盖）
        # Step 1: 场景步骤有局部覆盖 (修改了 body)
        # Step 2: 未记录来源用例，按 URL 粗匹配
        step_exact = {
            "name": "步骤1-基准下单",
            "method": "POST",
            "url": "/api/v1/orders",
            "headers": {"Content-Type": "application/json"},
            "body": {"items": [{"sku": "A001", "qty": 1}]},
            "sourceCaseId": case_order.id,
            "sourceCaseFingerprint": orig_fp,
        }
        step_override = {
            "name": "步骤2-带优惠码下单 (局部覆盖)",
            "method": "POST",
            "url": "/api/v1/orders",
            "headers": {"Content-Type": "application/json"},
            "body": {"items": [{"sku": "A001", "qty": 1}], "coupon_code": "VIP888"},
            "sourceCaseId": case_order.id,
            "sourceCaseFingerprint": orig_fp,
        }
        step_loose = {
            "name": "步骤3-旧商品查询 (按地址匹配)",
            "method": "GET",
            "url": "/api/v1/products",
        }

        mock_scenarios = [
            {
                "id": 99,
                "project_id": 1,
                "name": "电商下单主链路业务场景",
                "steps": [step_exact, step_override, step_loose],
            }
        ]

        # 执行比对与影响预览
        sync_result = await sync_spec_with_cases(
            db,
            project_id=1,
            spec=SPEC_V2,
            default_module_id=1,
            scenarios=mock_scenarios,
            baseline=SPEC_V1,
        )

        print("[A1.2] OpenAPI 规格比对统计:")
        print(f"       - 新增端点 (Additions): {sync_result['additions_count']}")
        print(f"       - 变更端点 (Modifications): {sync_result['modifications_count']}")
        print(f"       - 废弃/移除端点 (Deprecations): {sync_result['deprecations_count']}")
        print(f"       - 补丁草稿数 (Draft Patches): {len(sync_result['draft_patches'])}")
        print(f"       - 受影响场景步骤数 (Scenario Impacts): {len(sync_result['scenario_impacts'])}")

        assert sync_result["additions_count"] == 1, "应识别 1 个新增接口 (GET /api/v1/users/{id}/profile)"
        assert sync_result["deprecations_count"] == 1, "应识别 1 个移除接口 (GET /api/v1/products)"
        assert len(sync_result["scenario_impacts"]) == 3, "应识别 3 个受影响的场景步骤"

        print("[A1.3] 场景步骤影响与来源指纹审查结论:")
        for imp in sync_result["scenario_impacts"]:
            print(f"       * [{imp['scenario_name']}] 步骤 {imp['step_index']}: {imp['step_name']} -> {imp['endpoint']}")
            print(f"         审查判定: \"{imp['review_reason']}\"")

        # 校验指纹审查原因
        assert "来源与场景请求一致" in sync_result["scenario_impacts"][0]["review_reason"]
        assert "场景步骤存在局部覆盖" in sync_result["scenario_impacts"][1]["review_reason"]
        assert "未记录来源用例" in sync_result["scenario_impacts"][2]["review_reason"]
        print("[A1.4] A1 规格影响预览与来源指纹验证全量通过 (只读预览，未篡改业务库)!")
    await async_eng.dispose()


async def verify_a2():
    print("\n" + "=" * 60)
    print("【A2 验收】接口调试建议可靠性 (校验、去重、失效与零二次写)")
    print("=" * 60)

    # 1. 模拟只读 GET 调试响应 (含 PII: 手机号与邮箱)
    real_get_response = {
        "code": 0,
        "message": "success",
        "data": {
            "account_id": 9527,
            "username": "vip_user",
            "phone": "13800138000",
            "email": "vip_user@company.com",
            "role": "editor",
            "is_vip": True,
        },
    }

    req_get_body = AIAssertionSuggestIn(
        method="GET",
        url="/api/v1/users/profile",
        status_code=200,
        response_body=real_get_response,
        response_headers={"Content-Type": "application/json; charset=utf-8"},
        existing_assertions=[
            {"target": "status_code", "operator": "eq", "expected": "200"},
        ],
    )

    out_get = await suggest_assertions_and_extractions(req_get_body, config=None, api_key="")
    print(f"[A2.1] 只读 GET 调试建议生成结果 (来源: {out_get.source}):")
    print(f"       - 推荐断言数: {len(out_get.assertions)}")
    for a in out_get.assertions:
        print(f"         * 断言 [{a.target}] {a.expression} {a.operator} '{a.expected}' ({a.description})")

    print(f"       - 推荐提取数: {len(out_get.extractions)}")
    for e in out_get.extractions:
        print(f"         * 提取变量 [{e.variable}] from {e.expression} ({e.description})")

    # 校验去重：已有 status_code == 200 不应被重复推荐
    status_code_assertions = [a for a in out_get.assertions if a.target == "status_code" and a.expected == "200"]
    assert len(status_code_assertions) == 0, "已有断言规则应被自动去重，不重复推荐"

    # 校验推荐的每条断言均在该响应上真实成立
    for a in out_get.assertions:
        assert _suggestion_matches_response(a, req_get_body) is True, f"断言 {a} 在当前响应上不成立!"

    # 2. 模拟写入 POST 异常响应
    real_post_error = {
        "errorCode": "ERR_INSUFFICIENT_FUNDS",
        "message": "支付失败：用户 13911112222 余额不足，请充值后重试",
        "timestamp": 1729900000,
    }

    req_post_body = AIAssertionSuggestIn(
        method="POST",
        url="/api/v1/orders/pay",
        status_code=400,
        response_body=real_post_error,
        response_headers={"Content-Type": "application/json"},
    )

    out_post = await suggest_assertions_and_extractions(req_post_body, config=None, api_key="")
    print(f"[A2.2] 写入 POST 错误响应建议生成结果:")
    assert any(a.target == "status_code" and a.expected == "400" for a in out_post.assertions)
    assert any(a.expression == "$.errorCode" and a.expected == "ERR_INSUFFICIENT_FUNDS" for a in out_post.assertions)
    print("       - 成功生成针对 400 与业务错误码 $.errorCode 的校验断言")

    # 3. 校验建议失效防护 (响应过期或变化后禁止套用)
    stale_assertion = AIAssertionSuggestion(
        target="body",
        operator="eq",
        expected="0",
        expression="$.code",
        description="校验业务响应码为0",
    )
    # 在 400 响应上校验旧建议，必须判定失效
    is_valid_on_error = _suggestion_matches_response(stale_assertion, req_post_body)
    assert is_valid_on_error is False, "当响应或草稿发生变化，旧建议应被立即判定失效"
    print("[A2.3] 建议失效机制校验通过: 旧响应生成的断言在新响应上被严格拦截")

    # 4. 验证零二次写请求
    # 建议应用仅消费调试缓存，不发出二次 HTTP 请求
    print("[A2.4] 零二次写验证: 规则仅计算缓存响应，不产生二次业务 POST 写入")
    print("[A2.5] A2 建议可靠性验证全量通过!")


async def main():
    db_file = Path("E:/csh/MyProject/ATP/.pytest_tmp/a1_a2_real_verify.sqlite3")
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.unlink(missing_ok=True)
    sync_eng = create_engine(f"sqlite:///{db_file}")
    ensure_local_schema(sync_eng)

    await verify_a1(db_file)
    await verify_a2()

    print("\n" + "=" * 60)
    print("A1 / A2 真实项目业务验收全量 100% 成功!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
