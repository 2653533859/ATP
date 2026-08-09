import pytest

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
