import logging
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core import slow_query


class _FakeConn:
    def __init__(self):
        self.info = {}


def test_below_threshold_no_warning(caplog):
    with caplog.at_level(logging.WARNING):
        emitted = slow_query.maybe_emit_warning(50.0, "SELECT 1", None, 1000)
    assert emitted is False
    assert "slow_query" not in caplog.text


def test_above_threshold_emits_warning_with_trace(caplog, monkeypatch):
    monkeypatch.setattr(slow_query, "_trace_id_safe", lambda: "abc123")
    with caplog.at_level(logging.WARNING):
        emitted = slow_query.maybe_emit_warning(1500.0, "SELECT 1", None, 1000)
    assert emitted is True
    assert "slow_query" in caplog.text
    assert "abc123" in caplog.text
    assert "1500" in caplog.text


def test_sql_truncated_to_500_chars(caplog):
    long_sql = "SELECT " + "x" * 600
    with caplog.at_level(logging.WARNING):
        slow_query.maybe_emit_warning(2000.0, long_sql, None, 1000)
    msg = caplog.records[-1].getMessage()
    sql_part = msg.split("sql=", 1)[1].split(" params=", 1)[0]
    assert len(sql_part) == 500
    assert "x" * 600 not in msg


def test_params_truncated_to_200_chars(caplog):
    long_params = {"key": "v" * 500}
    with caplog.at_level(logging.WARNING):
        slow_query.maybe_emit_warning(2000.0, "SELECT 1", long_params, 1000)
    msg = caplog.records[-1].getMessage()
    # repr(...)[:200]
    assert "params=" in msg


def test_before_after_cursor_handler_pair(caplog):
    conn = _FakeConn()
    slow_query.on_before_cursor_execute(conn, None, "SELECT 1", None, None, False)
    assert "atp_query_start" in conn.info
    time.sleep(0.001)
    handler = slow_query.make_after_cursor_handler(threshold_ms=1)
    with caplog.at_level(logging.WARNING):
        handler(conn, None, "SELECT 1", None, None, False)
    # start key 已 pop
    assert "atp_query_start" not in conn.info


def test_after_cursor_handler_without_start_no_crash():
    conn = _FakeConn()
    handler = slow_query.make_after_cursor_handler(threshold_ms=1000)
    # 没调过 before：不应抛
    handler(conn, None, "SELECT 1", None, None, False)
