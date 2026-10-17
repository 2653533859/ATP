"""双端 UI 与状态树对齐分析器单测 (T2.1)"""

from __future__ import annotations

from app.services.parity_alignment_analyzer import (
    AlignmentMatchType,
    ParityAlignmentMatrix,
    ParityNode,
    ParityScreenTree,
    align_screen_trees,
)


def test_parity_node_flatten():
    root = ParityNode(
        node_id="root",
        role="container",
        children=[
            ParityNode(
                node_id="header",
                role="container",
                children=[
                    ParityNode(node_id="title", role="label", text="商城首页"),
                ],
            ),
            ParityNode(node_id="btn_buy", role="button", text="立即购买"),
        ],
    )
    all_nodes = root.flatten()
    assert len(all_nodes) == 4
    ids = [n.node_id for n in all_nodes]
    assert "root" in ids
    assert "title" in ids
    assert "btn_buy" in ids


def test_align_screen_trees_exact_and_synonym():
    # iOS 界面树: 包含搜索输入框、立即购买按钮、Apple Pay 按钮
    ios_tree = ParityScreenTree(
        screen_id="scr_ios_01",
        screen_name="商品详情主页",
        platform="ios",
        root_node=ParityNode(
            node_id="ios_root",
            role="container",
            children=[
                ParityNode(node_id="ios_input", role="input", text="搜索商品", identifier="search_box"),
                ParityNode(node_id="ios_buy", role="button", text="立即支付", identifier="btn_checkout"),
                ParityNode(node_id="ios_face_id", role="button", text="FaceID 生物识别设置", identifier="btn_face_id"),
            ],
        ),
    )

    # Android 界面树: 包含搜索输入框、确认付款按钮 (同义词)、微信支付按钮 (Android 独有)
    android_tree = ParityScreenTree(
        screen_id="scr_android_01",
        screen_name="商品详情主页",
        platform="android",
        root_node=ParityNode(
            node_id="android_root",
            role="container",
            children=[
                ParityNode(
                    node_id="android_input", role="input", text="搜索商品", identifier="com.shop:id/search_edit"
                ),
                ParityNode(
                    node_id="android_pay",
                    role="button",
                    text="确认付款 (微信/支付宝)",
                    identifier="com.shop:id/pay_btn",
                ),
                ParityNode(
                    node_id="android_apk",
                    role="button",
                    text="导出本地 APK 安装包",
                    identifier="com.shop:id/export_apk",
                ),
            ],
        ),
    )

    matrix = align_screen_trees(ios_tree, android_tree)
    assert isinstance(matrix, ParityAlignmentMatrix)
    assert matrix.screen_name == "商品详情主页"
    assert matrix.total_source_nodes == 3
    assert matrix.total_target_nodes == 3

    # 成功对齐 2 对 (搜索输入框 + 支付按钮同义词)
    assert matrix.aligned_pairs_count == 2

    # 查验对齐类型
    match_types = [p.match_type for p in matrix.aligned_pairs]
    assert AlignmentMatchType.EXACT in match_types
    assert AlignmentMatchType.SYNONYM in match_types or AlignmentMatchType.FUZZY in match_types

    # 查验单端独有控件
    # iOS 独有: FaceID
    assert matrix.source_only_count == 1
    assert matrix.source_only_nodes[0].node_id == "ios_face_id"

    # Android 独有: 导出 APK
    assert matrix.target_only_count == 1
    assert matrix.target_only_nodes[0].node_id == "android_apk"

    # 对齐率 2 / 3 = 0.6667
    assert matrix.overall_alignment_rate >= 0.65

    # 序列化字典校验
    d = matrix.to_dict()
    assert d["matrix_id"].startswith("matrix_")
    assert d["source_platform"] == "ios"
    assert d["target_platform"] == "android"
    assert len(d["aligned_pairs"]) == 2
    assert len(d["source_only_nodes"]) == 1
    assert len(d["target_only_nodes"]) == 1
