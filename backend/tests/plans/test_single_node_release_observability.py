"""Contracts for the standalone single-node release observability profile."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_single_node_prometheus_scrapes_current_host_network_components():
    config = yaml.safe_load(
        (ROOT / "deploy" / "observability" / "prometheus.single-node.yml").read_text(encoding="utf-8")
    )

    jobs = {item["job_name"]: item for item in config["scrape_configs"]}
    assert set(jobs) == {"atp-backend", "atp-worker", "atp-performance-worker", "prometheus"}
    assert jobs["atp-backend"]["static_configs"][0]["targets"] == ["host.docker.internal:8000"]
    assert jobs["atp-worker"]["static_configs"][0]["targets"] == ["host.docker.internal:9091"]
    assert jobs["atp-performance-worker"]["static_configs"][0]["targets"] == ["host.docker.internal:9092"]
    assert config["rule_files"] == ["/etc/prometheus/rules/atp.rules.yml"]


def test_single_node_prometheus_retains_calibration_window_and_is_loopback_only():
    compose = yaml.safe_load(
        (ROOT / "deploy" / "observability" / "docker-compose.single-node.yml").read_text(encoding="utf-8")
    )
    service = compose["services"]["prometheus"]

    assert "--storage.tsdb.retention.time=15d" in service["command"]
    assert service["ports"] == ["127.0.0.1:39090:9090"]
    assert service["extra_hosts"] == ["host.docker.internal:host-gateway"]
    assert service["restart"] == "unless-stopped"
    assert "no-new-privileges:true" in service["security_opt"]


def test_single_node_prometheus_rules_cover_targets_and_slo_guardrails():
    rules = yaml.safe_load((ROOT / "deploy" / "observability" / "prometheus.rules.yml").read_text(encoding="utf-8"))
    alerts = {item["alert"]: item for group in rules["groups"] for item in group["rules"]}

    assert set(alerts) == {
        "AtpReleaseTargetDown",
        "AtpApiErrorRateHigh",
        "AtpApiP95LatencyHigh",
        "AtpRunSuccessRateLow",
    }
    assert alerts["AtpReleaseTargetDown"]["for"] == "2m"
    assert 'http_requests_total{job="atp-backend",status="5xx"}' in alerts["AtpApiErrorRateHigh"]["expr"]
    assert "http_request_duration_seconds_bucket" in alerts["AtpApiP95LatencyHigh"]["expr"]
    assert "atp_run_outcomes_total" in alerts["AtpRunSuccessRateLow"]["expr"]


def test_grafana_api_error_alert_uses_grouped_status_and_low_traffic_ratio():
    config = yaml.safe_load((ROOT / "deploy" / "grafana" / "alerts" / "atp-alerts.yaml").read_text(encoding="utf-8"))
    rules = [rule for group in config["groups"] for rule in group["rules"]]
    api_rule = next(rule for rule in rules if rule["uid"] == "atp-api-error-rate")
    expression = next(item["model"]["expr"] for item in api_rule["data"] if item["refId"] == "A")

    assert 'http_requests_total{status="5xx"}' in expression
    assert "clamp_min(sum(rate(http_requests_total[5m])), 1e-9)" in expression


def test_redis_override_enables_acl_and_every_second_aof():
    compose = yaml.safe_load(
        (ROOT / "deploy" / "runtime-overrides" / "redis-acl-aof.override.yml").read_text(encoding="utf-8")
    )
    command = compose["services"]["redis"]["command"]

    assert command[:5] == ["redis-server", "--requirepass", "${REDIS_PASSWORD}", "--aclfile", "/data/users.acl"]
    assert command[command.index("--appendonly") + 1] == "yes"
    assert command[command.index("--appendfsync") + 1] == "everysec"
    assert command[command.index("--aof-use-rdb-preamble") + 1] == "yes"
