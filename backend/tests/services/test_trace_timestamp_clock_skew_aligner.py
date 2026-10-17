"""测试步骤与服务端调用链跨网络时钟对齐服务单测 (T2.1)"""

from __future__ import annotations

from app.services.trace_timestamp_clock_skew_aligner import (
    align_span_tree_timestamps,
    calculate_clock_skew,
    clear_clock_skew_history,
    list_clock_skew_history,
)


def test_calculate_clock_skew_ideal_and_skewed():
    clear_clock_skew_history()

    # 1. 理想状态：客户端发于 1000，收于 1100 (总 100ms)；服务端耗时 60ms (1020 到 1080)
    # 单程 RTT 为 20ms，时钟偏移应为 0
    ideal = calculate_clock_skew(
        client_send_time_ms=1000.0,
        client_receive_time_ms=1100.0,
        raw_server_start_ms=1020.0,
        raw_server_end_ms=1080.0,
        service_name="order-service",
    )
    assert ideal.skew_offset_ms == 0.0
    assert ideal.estimated_rtt_ms == 40.0
    assert ideal.is_skew_detected is False
    assert ideal.causality_preserved is True

    # 2. 时钟正偏 50ms：服务端时钟比客户端快 50ms
    # 导致 raw_server_start = 1070, raw_server_end = 1130 (服务端结束甚至看起来比客户端接收还晚)
    skewed = calculate_clock_skew(
        client_send_time_ms=1000.0,
        client_receive_time_ms=1100.0,
        raw_server_start_ms=1070.0,
        raw_server_end_ms=1130.0,
        service_name="order-service",
    )
    assert skewed.skew_offset_ms == 50.0  # 精准估算出 50ms 偏移
    assert skewed.is_skew_detected is True
    # 校准后时间戳自动缩减 50ms，恢复为 [1020, 1080]
    assert skewed.calibrated_server_start_ms == 1020.0
    assert skewed.calibrated_server_end_ms == 1080.0
    assert skewed.causality_preserved is True


def test_align_span_tree_timestamps():
    clear_clock_skew_history()

    client_step_span = {
        "span_id": "client_step_01",
        "start_time_ms": 2000.0,
        "end_time_ms": 2200.0,
        "name": "Step 1: 下单接口",
    }

    # 服务端微服务调用链存在 +40ms 时钟偏离
    server_spans = [
        {
            "span_id": "gateway_span",
            "parent_span_id": "client_step_01",
            "service_name": "api-gateway",
            "start_time_ms": 2060.0,  # 实际应为 2020
            "end_time_ms": 2220.0,  # 实际应为 2180
        },
        {
            "span_id": "db_query_span",
            "parent_span_id": "gateway_span",
            "service_name": "order-db",
            "start_time_ms": 2080.0,  # 实际应为 2040
            "end_time_ms": 2140.0,  # 实际应为 2100
        },
    ]

    aligned = align_span_tree_timestamps(client_step_span, server_spans)
    assert len(aligned) == 2

    # 查验第一个服务校准后是否被补偿
    assert aligned[0]["clock_skew_compensated"] is True
    assert aligned[0]["start_time_ms"] >= 2000.0
    assert aligned[0]["end_time_ms"] <= 2200.0

    # 查验第二个数据库服务是否同样被对齐
    assert aligned[1]["clock_skew_compensated"] is True
    assert aligned[1]["start_time_ms"] >= aligned[0]["start_time_ms"]
    assert aligned[1]["end_time_ms"] <= aligned[0]["end_time_ms"]

    history = list_clock_skew_history(limit=5)
    assert len(history) >= 1
