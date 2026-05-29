import json
from pathlib import Path

from app.services.performance import parse_k6_summary

ROOT = Path(__file__).resolve().parents[3]


def test_parse_k6_summary_extracts_core_http_metrics():
    parsed = parse_k6_summary(
        {
            "metrics": {
                "http_reqs": {"values": {"count": 42, "rate": 14.2}},
                "http_req_duration": {"values": {"p(95)": 321.5, "p(99)": 480.25}},
                "http_req_failed": {
                    "values": {"rate": 0.01},
                    "thresholds": {"rate<0.01": {"ok": False}},
                },
                "iterations": {"values": {"count": 40}},
                "data_received": {"values": {"count": 2048}},
                "data_sent": {"values": {"count": 512}},
            }
        }
    )

    assert parsed == {
        "executor": "k6",
        "rps": 14.2,
        "p95_ms": 321.5,
        "p99_ms": 480.25,
        "error_rate": 0.01,
        "iterations": 40,
        "data_received": 2048,
        "data_sent": 512,
        "thresholds": {"http_req_failed": {"rate<0.01": {"ok": False}}},
    }


def test_parse_k6_summary_tolerates_missing_metrics():
    parsed = parse_k6_summary({})

    assert parsed["executor"] == "k6"
    assert parsed["rps"] is None
    assert parsed["p95_ms"] is None
    assert parsed["thresholds"] == {}


def test_parse_k6_summary_matches_demo_fixture():
    fixture = json.loads(
        (ROOT / "docs" / "fixtures" / "performance-k6-summary.sample.json").read_text(encoding="utf-8")
    )

    parsed = parse_k6_summary(fixture)

    assert parsed["rps"] == 2.171620587154993
    assert parsed["p95_ms"] == 369.74464
    assert parsed["p99_ms"] is None
    assert parsed["error_rate"] == 0
    assert parsed["iterations"] == 12
    assert parsed["data_received"] == 61606
    assert parsed["data_sent"] == 3118
    assert parsed["thresholds"] == {
        "http_req_duration": {"p(95)<500": {"ok": True}},
        "http_req_failed": {"rate<0.01": {"ok": True}},
    }
