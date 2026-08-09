import pytest

from app.services.performance_metric_boundary import PerformanceMetricBoundaryError, build_metric_boundary


def test_metric_boundary_distinguishes_worker_platform_and_target_service():
    result = build_metric_boundary({"target_metrics": {"url_env": "PROMETHEUS_URL"}})

    assert result["worker"]["source"] == "performance-worker"
    assert result["platform"]["enabled"] is False
    assert result["target_service"]["configured"] is True
    assert result["target_service"]["collection"] == "boundary-only"


def test_metric_boundary_requires_a_target_endpoint():
    with pytest.raises(PerformanceMetricBoundaryError):
        build_metric_boundary({"target_metrics": {"query": "rate(http_requests_total[1m])"}})
