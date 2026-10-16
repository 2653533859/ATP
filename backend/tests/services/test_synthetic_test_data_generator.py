"""生产级测试合成数据生成器单元测试 (T3.2)。"""

from __future__ import annotations

import pytest
from app.services.synthetic_test_data_generator import (
    GenerationMode,
    clear_synthetic_data_store,
    generate_synthetic_dataset,
    get_synthetic_dataset_batch,
    list_synthetic_dataset_batches,
)


@pytest.fixture(autouse=True)
def _reset_data_state():
    clear_synthetic_data_store()
    yield
    clear_synthetic_data_store()


def test_generate_synthetic_dataset_multi_modal():
    """测试三模态（正向、边界极限、负向异常）合成数据生成。"""
    rules = [
        {"field_name": "user_age", "data_type": "integer", "min_value": 18, "max_value": 65},
        {"field_name": "user_email", "data_type": "email"},
        {"field_name": "user_phone", "data_type": "phone"},
        {"field_name": "user_status", "data_type": "enum", "enum_values": ["ACTIVE", "SUSPENDED", "PENDING"]},
        {"field_name": "account_balance", "data_type": "float", "min_value": 0.0, "max_value": 50000.0},
    ]

    batch = generate_synthetic_dataset(
        dataset_name="user_onboarding",
        rules=rules,
        row_count=14,
    )

    assert batch.dataset_name == "user_onboarding"
    assert batch.total_rows == 14
    assert batch.fields_count == 5
    assert batch.positive_count > 0
    assert batch.boundary_count > 0
    assert batch.negative_count > 0

    # 验证正向数据行
    pos_rows = [r for r in batch.rows if r.mode == GenerationMode.POSITIVE_VALID]
    for r in pos_rows:
        assert r.is_expected_valid is True
        age = r.data["user_age"]
        assert 18 <= age <= 65
        assert "@" in r.data["user_email"]
        assert r.data["user_status"] in ["ACTIVE", "SUSPENDED", "PENDING"]

    # 验证负向异常行
    neg_rows = [r for r in batch.rows if r.mode == GenerationMode.NEGATIVE_ANOMALY]
    for r in neg_rows:
        assert r.is_expected_valid is False
        assert r.anomaly_field is not None
        assert r.anomaly_reason is not None

    # 验证持久化
    saved = get_synthetic_dataset_batch(batch.batch_id)
    assert saved is not None
    assert saved.batch_id == batch.batch_id


def test_generate_string_boundary_edge():
    """测试边界值探测模式生成。"""
    rules = [
        {"field_name": "coupon_code", "data_type": "string", "min_length": 6, "max_length": 12},
    ]

    batch = generate_synthetic_dataset(dataset_name="coupons", rules=rules, row_count=4)
    # 第 4 行根据轮转是 BOUNDARY_EDGE
    bound_rows = [r for r in batch.rows if r.mode == GenerationMode.BOUNDARY_EDGE]
    assert len(bound_rows) >= 1
    code_val = bound_rows[0].data["coupon_code"]
    assert len(code_val) == 6  # 正好触及 min_length 边界


def test_list_and_clear_batches():
    """测试批次查询与清空。"""
    rules = [{"field_name": "score", "data_type": "integer"}]
    generate_synthetic_dataset("scores", rules, row_count=5)

    batches = list_synthetic_dataset_batches()
    assert len(batches) == 1

    clear_synthetic_data_store()
    assert len(list_synthetic_dataset_batches()) == 0
