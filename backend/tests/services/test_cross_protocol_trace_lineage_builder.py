"""跨协议多跳调用链拓扑血缘重构服务单测 (T2.3)"""

from __future__ import annotations

from app.services.cross_protocol_trace_lineage_builder import (
    build_cross_protocol_lineage,
    clear_topology_lineage_store,
    get_topology_lineage,
    list_topology_lineages,
)


def test_build_cross_protocol_lineage():
    clear_topology_lineage_store()

    trace_id = "e87b2f3577b34da6a3ce929d0e0e8899"

    # 包含 HTTP Gateway -> gRPC Auth -> HTTP Order -> Kafka Producer -> Postgres 的多协议调用链
    spans = [
        {
            "span_id": "span_gw",
            "name": "HTTP POST /order/create",
            "service_name": "api-gateway",
            "duration_ms": 150.0,
            "start_time_ms": 1000.0,
            "end_time_ms": 1150.0,
            "attributes": {"http.method": "POST"},
        },
        {
            "span_id": "span_auth",
            "parent_span_id": "span_gw",
            "name": "VerifyToken",
            "service_name": "auth-center",
            "duration_ms": 30.0,
            "start_time_ms": 1010.0,
            "end_time_ms": 1040.0,
            "attributes": {"rpc.system": "grpc"},
        },
        {
            "span_id": "span_order",
            "parent_span_id": "span_gw",
            "name": "CreateOrder",
            "service_name": "order-service",
            "duration_ms": 90.0,
            "start_time_ms": 1050.0,
            "end_time_ms": 1140.0,
            "attributes": {"http.status_code": 200},
        },
        {
            "span_id": "span_kafka",
            "parent_span_id": "span_order",
            "name": "ProduceOrderPaidEvent",
            "service_name": "order-service",
            "duration_ms": 20.0,
            "start_time_ms": 1060.0,
            "end_time_ms": 1080.0,
            "attributes": {"messaging.system": "kafka"},
        },
        {
            "span_id": "span_db",
            "parent_span_id": "span_order",
            "name": "INSERT INTO orders",
            "service_name": "order-db",
            "duration_ms": 40.0,
            "start_time_ms": 1090.0,
            "end_time_ms": 1130.0,
            "attributes": {"db.system": "postgresql"},
        },
    ]

    lineage = build_cross_protocol_lineage(trace_id, spans)

    assert lineage.total_spans == 5
    assert lineage.services_count == 4  # api-gateway, auth-center, order-service, order-db
    assert lineage.max_depth_hops == 3  # gw -> order -> db/kafka
    assert "grpc" in lineage.protocols_covered
    assert "kafka" in lineage.protocols_covered
    assert "postgresql" in lineage.protocols_covered
    assert "http" in lineage.protocols_covered

    # 验证关键路径计算 (gw -> order -> db)
    assert len(lineage.critical_path_span_ids) >= 2
    assert lineage.critical_path_span_ids[0] == "span_gw"
    assert lineage.critical_path_span_ids[1] == "span_order"

    # 验证服务拓扑边 (Edges)
    assert len(lineage.edges) >= 3

    # 查验单条记录查询
    stored = get_topology_lineage(trace_id)
    assert stored is not None
    assert stored["trace_id"] == trace_id

    # 查验列表查询
    items = list_topology_lineages(limit=10)
    assert len(items) == 1
