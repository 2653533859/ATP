"""Unit Tests for Adaptive Assertion Auto Patcher (T4.2)。"""

from __future__ import annotations

import pytest

from app.services.adaptive_assertion_auto_patcher import (
    PatchType,
    apply_assertion_patch,
    clear_assertion_patch_store,
    derive_adaptive_assertion_patch,
    list_assertion_patches,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_assertion_patch_store()
    yield
    clear_assertion_patch_store()


def test_derive_patch_envelope_unwrap():
    # 原用例直接检查顶级 order_id，接口重构后包裹进 data 节点
    original = "$.order_id == 1001"
    response_payload = {
        "code": 0,
        "message": "success",
        "data": {
            "order_id": 1001,
            "status": "PAID",
        },
    }

    patch = derive_adaptive_assertion_patch(
        case_id="case_api_101",
        original_assertion=original,
        actual_response_payload=response_payload,
        expected_value=1001,
    )

    assert patch.case_id == "case_api_101"
    assert patch.patch_type == PatchType.ENVELOPE_UNWRAP
    assert patch.confidence_score >= 0.85
    assert patch.patched_assertion == "$.data.order_id == 1001"
    assert "assert $.data.order_id == 1001" in patch.python_code_diff
    assert "data" in patch.explanation


def test_derive_patch_field_rename_snake_to_camel():
    # 原用例访问下划线 user_id，接口重构后转为小驼峰 userId
    original = "response['user_id'] == 888"
    response_payload = {
        "userId": 888,
        "userName": "Alice",
    }

    patch = derive_adaptive_assertion_patch(
        case_id="case_api_102",
        original_assertion=original,
        actual_response_payload=response_payload,
        expected_value=888,
    )

    assert patch.patch_type == PatchType.FIELD_RENAME
    assert patch.confidence_score >= 0.85
    assert "userId" in patch.patched_assertion
    assert patch.is_applied is False


def test_derive_patch_path_expansion_nested_list():
    # 原用例直接找 item_id，接口变为列表数组 items[0].item_id
    original = "$.item_id == 55"
    response_payload = {
        "total": 1,
        "items": [
            {"item_id": 55, "name": "MacBook Pro"},
        ],
    }

    patch = derive_adaptive_assertion_patch(
        case_id="case_api_103",
        original_assertion=original,
        actual_response_payload=response_payload,
        expected_value=55,
    )

    assert patch.patch_type == PatchType.PATH_EXPANSION
    assert "items[0].item_id" in patch.patched_assertion


def test_apply_patch_lifecycle_and_crud():
    patch = derive_adaptive_assertion_patch(
        case_id="case_crud_1",
        original_assertion="$.code == 200",
        actual_response_payload={"code": 200},
    )

    assert len(list_assertion_patches()) == 1
    assert patch.is_applied is False

    # 应用补丁
    ok = apply_assertion_patch(patch.patch_id)
    assert ok is True
    assert patch.is_applied is True

    # 再次查询验证
    applied_list = list_assertion_patches(case_id="case_crud_1")
    assert len(applied_list) == 1
    assert applied_list[0].is_applied is True
