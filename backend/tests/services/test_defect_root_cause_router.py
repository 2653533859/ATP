"""故障责任微服务与团队智能归因路由器单测 (T2.1)"""

from __future__ import annotations

from app.services.defect_root_cause_router import (
    DefectRootCauseType,
    attribute_defect_root_cause,
)


def test_attribute_payment_database_timeout():
    msg = "PostgreSQL deadlock timeout on payment table at 0x7fa"
    stack = '  File "/app/services/payment.py", line 40, in charge\n    db.commit()'

    attr = attribute_defect_root_cause(
        error_message=msg,
        stack_trace=stack,
        target_endpoint="/api/v1/payment/checkout",
    )
    assert attr.responsible_service == "payment-service"
    assert attr.root_cause_type == DefectRootCauseType.DATABASE_TIMEOUT_OR_DEADLOCK
    assert "结算" in attr.responsible_team
    assert attr.suggested_assignee == "lead_payment@atp.io"
    assert attr.attribution_confidence_pct >= 85.0
    assert len(attr.evidence_chain) >= 2


def test_attribute_auth_token_expired():
    msg = "JWT token expired: signature verification failed"
    stack = '  File "/app/middleware/auth.py", line 20, in authenticate\n    raise Unauthorized("Expired")'

    attr = attribute_defect_root_cause(
        error_message=msg,
        stack_trace=stack,
        target_endpoint="/api/v1/user/profile",
    )
    assert attr.responsible_service == "auth-service"
    assert attr.root_cause_type == DefectRootCauseType.AUTH_TOKEN_EXPIRED_OR_FORBIDDEN
    assert attr.suggested_assignee == "sec_lead@atp.io"
    assert "安全" in attr.responsible_team


def test_attribute_downstream_crash():
    msg = "502 Bad Gateway: upstream order-service connection reset by peer"
    stack = '  File "/gateway/router.py", line 50, in proxy_pass\n    await fetch()'

    attr = attribute_defect_root_cause(
        error_message=msg,
        stack_trace=stack,
        target_endpoint="/api/v1/orders/create",
    )
    assert attr.responsible_service == "order-service"
    assert attr.root_cause_type == DefectRootCauseType.DOWNSTREAM_SERVICE_CRASH
    assert attr.suggested_assignee == "order_dev@atp.io"


def test_attribute_with_custom_ownership():
    msg = "InventorySkuNotAvailableError: SKU out of stock"
    stack = '  File "/app/services/inventory.py", line 12, in check\n    pass'

    custom_map = {
        "inventory-service": {
            "team": "供应链专班",
            "assignee": "supply_expert@atp.io",
            "name": "供应链专家",
        }
    }

    attr = attribute_defect_root_cause(
        error_message=msg,
        stack_trace=stack,
        custom_ownership_map=custom_map,
    )
    assert attr.responsible_service == "inventory-service"
    assert attr.responsible_team == "供应链专班"
    assert attr.suggested_assignee == "supply_expert@atp.io"

    d = attr.to_dict()
    assert d["responsible_service"] == "inventory-service"
    assert d["root_cause_type"] == "BUSINESS_ASSERTION_FAILED"
