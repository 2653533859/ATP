import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_storage_usage_metrics_are_defined_as_gauges():
    content = repo_path("backend/app/core/metrics.py").read_text(encoding="utf-8")

    assert "from prometheus_client import Counter, Gauge, Histogram" in content
    assert "def _gauge(" in content
    assert 'STORAGE_TOTAL_BYTES = _gauge("atp_storage_total_bytes"' in content
    assert 'STORAGE_TOTAL_OBJECTS = _gauge("atp_storage_total_objects"' in content


def test_storage_stats_endpoint_refreshes_minio_metrics():
    content = repo_path("backend/app/api/v1/storage.py").read_text(encoding="utf-8")

    assert "from app.core.metrics import STORAGE_TOTAL_BYTES, STORAGE_TOTAL_OBJECTS" in content
    assert "STORAGE_TOTAL_BYTES.labels(bucket=stats.bucket).set(stats.total_bytes)" in content
    assert "STORAGE_TOTAL_OBJECTS.labels(bucket=stats.bucket).set(stats.total_object_count)" in content


def test_grafana_dashboard_covers_s4_observability_targets():
    dashboard = json.loads(repo_path("docker/grafana/dashboards/atp-overview.json").read_text(encoding="utf-8"))
    panels = {panel["title"]: panel for panel in dashboard["panels"]}

    assert "Slow queries (last 1h)" in panels
    assert "Slow query rate" in panels
    assert "Celery queue length" in panels
    assert "API 5xx error rate" in panels
    assert "MinIO storage bytes" in panels
    assert "MinIO object count" in panels

    api_expr = panels["API 5xx error rate"]["targets"][0]["expr"]
    assert 'http_requests_total{job="atp-backend",status=~"5.."}' in api_expr
    assert 'http_requests_total{job="atp-backend"}' in api_expr

    assert panels["MinIO storage bytes"]["targets"][0]["expr"] == "atp_storage_total_bytes"
    assert panels["MinIO object count"]["targets"][0]["expr"] == "atp_storage_total_objects"


def test_observability_docs_and_roadmap_include_minio_and_error_rate():
    doc = repo_path("docs/observability-guide.md").read_text(encoding="utf-8")
    roadmap = repo_path("docs/optimization-roadmap-2026.md").read_text(encoding="utf-8")

    assert "慢查询、队列积压、接口错误率与 MinIO 使用量" in doc
    assert "atp_storage_total_bytes" in doc
    assert "atp_storage_total_objects" in doc
    assert "API 5xx 错误率" in doc
    assert "MinIO 存储字节数" in doc
    assert "| S4-05 | 可观测性看板增强 | P2 | [x] 已完成 |" in roadmap
