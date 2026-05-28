import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core import metrics


def test_metrics_module_importable():
    """模块自身 import 不报错（无论是否装 prometheus_client）。"""
    assert hasattr(metrics, "STATS_CACHE")
    assert hasattr(metrics, "SLOW_QUERY")
    assert hasattr(metrics, "CELERY_TIMEOUT")
    assert hasattr(metrics, "RUN_RETENTION_DELETED")


def test_inc_and_labels_are_safe_no_matter_what():
    """无论 NOOP 还是真 Counter，inc/labels 调用都不应抛异常。"""
    metrics.SLOW_QUERY.inc()
    metrics.STATS_CACHE.labels(result="hit").inc()
    metrics.STATS_CACHE.labels(result="miss").inc()
    metrics.STATS_CACHE.labels(result="error").inc()
    metrics.CELERY_TIMEOUT.labels(kind="soft").inc()
    metrics.CELERY_TIMEOUT.labels(kind="hard").inc()
    metrics.RUN_RETENTION_DELETED.labels(model="test_runs").inc(5)


def test_enable_metrics_for_is_safe_without_dep():
    """缺 prometheus-fastapi-instrumentator 时 enable_metrics_for 不应抛。"""

    class _FakeApp:
        def add_middleware(self, *_a, **_kw):
            pass

        def get(self, *_a, **_kw):
            def decorator(fn):
                return fn

            return decorator

    metrics.enable_metrics_for(_FakeApp())


def test_counter_accumulates_when_prometheus_client_available():
    """有依赖时 Counter 应正确累加；无依赖时 _NOOP 跳过测试。"""
    if not metrics._PROMETHEUS_AVAILABLE:
        import pytest

        pytest.skip("prometheus_client not installed")

    before = metrics.SLOW_QUERY._value.get()  # type: ignore[attr-defined]
    metrics.SLOW_QUERY.inc()
    after = metrics.SLOW_QUERY._value.get()  # type: ignore[attr-defined]
    assert after == before + 1


def test_start_worker_metrics_server_disabled_by_port_zero():
    """WORKER_METRICS_PORT=0 时跳过启动，不抛异常。"""
    ok = metrics.start_worker_metrics_server(0)
    assert ok is False


def test_start_worker_metrics_server_handles_oserror(monkeypatch):
    """端口被占用时返回 False 但不抛异常（多 worker 子进程共享端口的预期行为）。"""
    if not metrics._PROMETHEUS_AVAILABLE:
        import pytest

        pytest.skip("prometheus_client not installed")

    import prometheus_client

    def _raise_oserror(_port):
        raise OSError(98, "Address already in use")

    monkeypatch.setattr(prometheus_client, "start_http_server", _raise_oserror)

    ok = metrics.start_worker_metrics_server(9091)
    assert ok is False


def test_start_worker_metrics_server_returns_true_on_success(monkeypatch):
    """成功路径：start_http_server 不抛异常时返回 True。"""
    if not metrics._PROMETHEUS_AVAILABLE:
        import pytest

        pytest.skip("prometheus_client not installed")

    import prometheus_client

    called = {"port": None}

    def _fake_start(port):
        called["port"] = port

    monkeypatch.setattr(prometheus_client, "start_http_server", _fake_start)

    ok = metrics.start_worker_metrics_server(9091)
    assert ok is True
    assert called["port"] == 9091
