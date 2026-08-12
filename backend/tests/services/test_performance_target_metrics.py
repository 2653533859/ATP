import json

import pytest

from app.services import performance_target_metrics
from app.services.performance_target_metrics import TargetMetricError, _extract_scalar, build_target_metric_sampler


def test_target_metric_sampler_is_bounded_and_extracts_scalar(monkeypatch):
    calls = []

    def fake_query(url, query, timeout):
        calls.append((url, query, timeout))
        return {"status": "success", "data": {"result": [{"value": ["1", "42.5"]}]}}

    monkeypatch.setattr("app.services.performance_target_metrics._query_prometheus", fake_query)
    sampler = build_target_metric_sampler(
        {"target_metrics": {"prometheus_url": "http://prometheus:9090", "queries": {"cpu": "up"}}}
    )

    result = sampler()

    assert result["source"] == "target-service-prometheus"
    assert result["metrics"] == {"cpu": 42.5}
    assert calls[0][0] == "http://prometheus:9090"


def test_target_metric_sampler_rejects_invalid_url_and_query_count():
    with pytest.raises(TargetMetricError):
        build_target_metric_sampler({"target_metrics": {"queries": {"cpu": "up"}}})
    with pytest.raises(TargetMetricError):
        build_target_metric_sampler({"target_metrics": {"url": "file:///tmp/prometheus", "queries": {"cpu": "up"}}})
    with pytest.raises(TargetMetricError):
        build_target_metric_sampler(
            {
                "target_metrics": {
                    "url": "http://prometheus:9090",
                    "queries": {str(index): "up" for index in range(9)},
                }
            }
        )


def test_target_metric_sampler_validates_resolved_worker_environment_host(monkeypatch):
    monkeypatch.setenv("ATP_PROM_URL", "http://internal.example.test:9090")

    with pytest.raises(TargetMetricError, match="allowlist"):
        build_target_metric_sampler(
            {
                "target_metrics": {
                    "url_env": "ATP_PROM_URL",
                    "queries": {"cpu": "up"},
                }
            },
            allowed_hosts=["prometheus.example.test"],
        )


def test_extract_scalar_handles_empty_result():
    assert _extract_scalar({"data": {"result": []}}) is None


def test_target_metric_sampler_supports_environment_url_and_reports_query_errors(monkeypatch):
    monkeypatch.setenv("ATP_PROM_URL", "https://prometheus.example.test:9090/base")
    calls = []

    def fake_query(url, query, timeout):
        calls.append((url, query, timeout))
        if query == "bad":
            raise TimeoutError("upstream timeout")
        return {"status": "success", "data": {"result": []}}

    monkeypatch.setattr(performance_target_metrics, "_query_prometheus", fake_query)
    sampler = build_target_metric_sampler(
        {
            "target_metrics": {
                "url_env": "ATP_PROM_URL",
                "timeout_seconds": 99,
                "queries": {"empty": "up", "failed": "bad"},
            }
        },
        allowed_hosts=["example.test"],
    )

    result = sampler()

    assert calls == [
        ("https://prometheus.example.test:9090/base", "up", 10.0),
        ("https://prometheus.example.test:9090/base", "bad", 10.0),
    ]
    assert result["metrics"] == {}
    assert result["errors"] == ["empty: no scalar result", "failed: upstream timeout"]


def test_target_metric_sampler_handles_empty_configuration_and_invalid_timeout(monkeypatch):
    assert build_target_metric_sampler({}) is None
    assert build_target_metric_sampler({"target_metrics": {"url": "http://prometheus:9090", "queries": {}}}) is None

    with pytest.raises(TargetMetricError, match="必须是 JSON 对象"):
        build_target_metric_sampler({"target_metrics": "invalid"})
    with pytest.raises(TargetMetricError, match="timeout_seconds"):
        build_target_metric_sampler(
            {
                "target_metrics": {
                    "url": "http://prometheus:9090",
                    "timeout_seconds": "invalid",
                    "queries": {"cpu": "up"},
                }
            }
        )

    monkeypatch.setattr(performance_target_metrics, "MAX_QUERIES", 1)
    with pytest.raises(TargetMetricError, match="不能超过"):
        build_target_metric_sampler(
            {"target_metrics": {"url": "http://prometheus:9090", "queries": {"a": "up", "b": "up"}}}
        )


def test_query_prometheus_validates_response_status_and_size(monkeypatch):
    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size):
            return self.body

    class Opener:
        def __init__(self, body):
            self.body = body

        def open(self, _request, timeout):
            assert timeout == 1.5
            return Response(self.body)

    success = json.dumps({"status": "success", "data": {"result": []}}).encode()
    monkeypatch.setattr(performance_target_metrics, "_TARGET_METRIC_OPENER", Opener(success))
    assert performance_target_metrics._query_prometheus("http://prometheus:9090", "up", 1.5)["status"] == "success"

    monkeypatch.setattr(
        performance_target_metrics,
        "_TARGET_METRIC_OPENER",
        Opener(json.dumps({"status": "error", "error": "bad query"}).encode()),
    )
    with pytest.raises(TargetMetricError, match="bad query"):
        performance_target_metrics._query_prometheus("http://prometheus:9090", "up", 1.5)

    monkeypatch.setattr(performance_target_metrics, "MAX_RESPONSE_BYTES", 2)
    monkeypatch.setattr(performance_target_metrics, "_TARGET_METRIC_OPENER", Opener(b"123"))
    with pytest.raises(TargetMetricError, match="大小限制"):
        performance_target_metrics._query_prometheus("http://prometheus:9090", "up", 1.5)


@pytest.mark.parametrize(
    "payload",
    [
        {"data": {"result": [{"value": ["time"]}]}},
        {"data": {"result": [{"value": ["time", "not-a-number"]}]}},
        {"data": {"result": ["invalid"]}},
    ],
)
def test_extract_scalar_rejects_malformed_values(payload):
    assert _extract_scalar(payload) is None
