"""Unit Tests for Incident Knowledge Fingerprint Matcher (T3.2)。"""

from __future__ import annotations

import pytest

from app.services.incident_knowledge_fingerprint_matcher import (
    MatchTier,
    clear_incident_knowledge_base,
    delete_known_incident,
    extract_error_fingerprint,
    list_known_incidents,
    match_incident_fingerprint,
    register_known_incident,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_incident_knowledge_base()
    yield
    clear_incident_knowledge_base()


def test_extract_error_fingerprint_cleans_noise():
    raw_error = "OperationalError: (1213, 'Deadlock found at 0x7ffd5a2c4e10 with uuid 12345678-1234-1234-1234-123456789abc when trying to get lock')"
    stack = 'File "/app/order_service.py", line 145, in checkout'
    service = "order-service"

    tokens = extract_error_fingerprint(raw_error, stack, service)

    # 验证 16 进制内存地址与 UUID 已被清洗，纯数字行号已被过滤
    assert "0x7ffd5a2c4e10" not in tokens
    assert "12345678-1234-1234-1234-123456789abc" not in tokens
    assert "145" not in tokens
    # 核心语义 token 被保留
    assert "deadlock" in tokens
    assert "lock" in tokens
    assert "checkout" in tokens
    assert "order" in tokens


def test_match_incident_fingerprint_similarity():
    # 1. 预先录入已知缺陷经验
    register_known_incident(
        title="MySQL 订单结算事务行锁并发争用死锁",
        category="DATABASE",
        service_name="order-service",
        error_pattern="Deadlock found when trying to get lock; try restarting transaction",
        root_cause_explanation="高并发下不同事务更新订单行与用户优惠券表的加锁顺序相反导致循环等待死锁。",
        verified_resolution="统一加锁顺序: 必须按 order_id 升序排列加锁，并调小 innodb_lock_wait_timeout。",
        external_ticket_ref="JIRA-4891",
        incident_id="inc_mysql_deadlock",
    )

    register_known_incident(
        title="Redis 连接池耗尽超时",
        category="TIMEOUT",
        service_name="cache-service",
        error_pattern="ConnectionPool timeout while waiting for connection",
        root_cause_explanation="Redis 连接池 max_connections 偏小且连接未在 finally 块释放导致泄露。",
        verified_resolution="连接池扩容至 200 并采用上下文管理器确保 auto-close。",
        external_ticket_ref="JIRA-5120",
        incident_id="inc_redis_timeout",
    )

    # 2. 模拟新发生的类似死锁报错 (带噪声)
    query_err = "pymysql.err.OperationalError: (1213, 'Deadlock found when trying to get lock at 0xdeadbeef')"
    query_stack = 'File "order_service.py", line 299, in execute_checkout'

    report = match_incident_fingerprint(
        error_message=query_err,
        stack_trace=query_stack,
        service_name="order-service",
        min_similarity=0.50,
    )

    assert report.matches_count >= 1
    top_match = report.matches[0]
    assert top_match.incident.incident_id == "inc_mysql_deadlock"
    assert top_match.match_tier in (MatchTier.HIGH_SIMILARITY, MatchTier.EXACT_MATCH)
    assert top_match.similarity_score >= 0.65
    assert "加锁顺序" in str(report.best_match_resolution)
    assert "JIRA-4891" in report.recommendation_summary


def test_match_incident_unmatched_new_problem():
    register_known_incident(
        title="已知问题A",
        category="OTHER",
        service_name="svc-a",
        error_pattern="specific strange error code 998244353",
        root_cause_explanation="desc a",
        verified_resolution="fix a",
    )

    report = match_incident_fingerprint(
        error_message="unrelated completely different error xyz",
        service_name="svc-b",
        min_similarity=0.80,
    )

    assert report.matches_count == 0
    assert report.best_match_resolution is None
    assert "未检索到" in report.recommendation_summary


def test_incident_knowledge_crud():
    item = register_known_incident(
        title="测试条目",
        category="TEST",
        service_name="s",
        error_pattern="err",
        root_cause_explanation="cause",
        verified_resolution="res",
        incident_id="inc_crud",
    )
    assert item.incident_id == "inc_crud"
    assert len(list_known_incidents()) == 1

    deleted = delete_known_incident("inc_crud")
    assert deleted is True
    assert len(list_known_incidents()) == 0
