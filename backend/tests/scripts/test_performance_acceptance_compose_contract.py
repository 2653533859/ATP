"""Contract checks for the isolated Linux performance acceptance stack."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_acceptance_compose_has_metrics_and_maintenance_services_without_cycle():
    compose = yaml.safe_load((ROOT / "docker-compose.performance-acceptance.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    prometheus = services["prometheus"]
    assert prometheus["ports"] == ["127.0.0.1:18090:9090"]
    assert "performance-worker" not in prometheus.get("depends_on", {})
    assert prometheus["healthcheck"]["test"][-1].endswith("/-/ready")

    performance_worker = services["performance-worker"]
    assert "redis" in performance_worker["depends_on"]
    assert "prometheus" in performance_worker["depends_on"]

    beat = services["beat"]
    assert beat["command"][-2:] == ["beat", "--loglevel=info"]
    assert beat["environment"]["CELERY_QUEUES"] == "maintenance"
    assert beat["environment"]["DB_BACKUP_ENABLED"] == "true"
    assert beat["environment"]["ADB_SCAN_ENABLED"] == "false"


def test_acceptance_prometheus_scrapes_backend_and_performance_worker():
    config = yaml.safe_load((ROOT / "deploy" / "performance-acceptance" / "prometheus.yml").read_text(encoding="utf-8"))
    jobs = {item["job_name"]: item for item in config["scrape_configs"]}

    assert jobs["atp-backend"]["static_configs"][0]["targets"] == ["backend:8000"]
    assert jobs["atp-performance-worker"]["static_configs"][0]["targets"] == ["performance-worker:9092"]
