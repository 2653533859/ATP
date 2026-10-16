"""多版本视觉黄金基线管理与跨分支追踪单元测试 (T1.3)。"""

from __future__ import annotations

import pytest
from app.services.visual_golden_baseline_branch_tracker import (
    BaselineEvolutionType,
    clear_baseline_tracker_store,
    compare_cross_branch_baselines,
    get_visual_baseline,
    list_visual_baselines,
    promote_baseline_to_golden,
    register_visual_baseline,
)


@pytest.fixture(autouse=True)
def _reset_baseline_state():
    clear_baseline_tracker_store()
    yield
    clear_baseline_tracker_store()


def test_register_and_promote_golden_baseline():
    """测试登记基线快照与提升为生效黄金基线。"""
    vps = {"DESKTOP": "hash_desktop_1001", "MOBILE": "hash_mobile_1001"}
    snap = register_visual_baseline(
        page_route="/checkout",
        branch_name="main",
        version_tag="v1.0.0",
        viewport_snapshots=vps,
        changelog="初始主干基线",
        is_active_golden=False,
    )

    assert snap.page_route == "/checkout"
    assert snap.branch_name == "main"
    assert snap.is_active_golden is False

    # 提升为黄金基线
    promote_res = promote_baseline_to_golden(snap.baseline_id, approver="lead_designer_chen")
    assert promote_res["success"] is True
    assert promote_res["baseline"]["is_active_golden"] is True
    assert promote_res["baseline"]["approved_by"] == "lead_designer_chen"

    saved = get_visual_baseline(snap.baseline_id)
    assert saved is not None
    assert saved.is_active_golden is True


def test_compare_cross_branch_identical():
    """测试跨分支基线完全相同时判定 IDENTICAL_BASELINE。"""
    vps = {"DESKTOP": "hash_same_01"}
    register_visual_baseline("/dashboard", "main", "v1.0", vps, is_active_golden=True)
    register_visual_baseline("/dashboard", "feat/perf-opt", "v1.0", vps, is_active_golden=True)

    report = compare_cross_branch_baselines("/dashboard", source_branch="feat/perf-opt", target_branch="main")
    assert report.has_viewport_drifts is False
    assert report.evolution_type == BaselineEvolutionType.IDENTICAL_BASELINE
    assert len(report.drifted_viewports) == 0


def test_compare_cross_branch_intentional_redesign():
    """测试重构改版变更识别为 INTENTIONAL_REDESIGN。"""
    vps_main = {"DESKTOP": "hash_old_desk", "MOBILE": "hash_old_mob"}
    vps_feat = {"DESKTOP": "hash_new_desk", "MOBILE": "hash_new_mob"}

    register_visual_baseline("/home", "main", "v1.0", vps_main, is_active_golden=True)
    register_visual_baseline(
        "/home", "feat/redesign", "v2.0", vps_feat, is_active_golden=True, changelog="首页全新视觉改版重构"
    )

    report = compare_cross_branch_baselines("/home", source_branch="feat/redesign", target_branch="main")
    assert report.has_viewport_drifts is True
    assert report.evolution_type == BaselineEvolutionType.INTENTIONAL_REDESIGN
    assert len(report.drifted_viewports) == 2


def test_list_and_clear_baselines():
    """测试按路由过滤与清空。"""
    register_visual_baseline("/p1", "main", "v1.0", {})
    register_visual_baseline("/p2", "main", "v1.0", {})

    all_bases = list_visual_baselines()
    assert len(all_bases) == 2

    filtered = list_visual_baselines(page_route="/p1")
    assert len(filtered) == 1

    clear_baseline_tracker_store()
    assert len(list_visual_baselines()) == 0
