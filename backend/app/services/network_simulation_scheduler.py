"""Mobile Network Simulation Test Scheduling and Metric Collection Service (Q1.2).

Orchestrates test executions under simulated network conditions (2G/3G/4G, loss, high latency):
1. Pre-execution network condition configuration and injection (CDP / ADB netem).
2. Runtime metric collection: request latency, timeouts, packet drops, retries, and network resilience score.
3. Post-execution network reset and teardown safety guarantees.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Any

from app.services.network_simulation import (
    calculate_network_transmission_delay,
    generate_adb_network_commands,
    generate_cdp_network_conditions,
    get_preset_network_profiles,
    is_packet_dropped,
)

logger = logging.getLogger(__name__)


class NetworkMetricsCollector:
    """Collects real-time network request and latency metrics under simulated throttling."""

    def __init__(self, profile_id: str, custom_profile: dict[str, Any] | None = None):
        presets = get_preset_network_profiles()
        self.profile = custom_profile or presets.get(profile_id) or presets["2g_edge"]
        self.profile_id = profile_id
        self.requests: list[dict[str, Any]] = []
        self.dropped_count = 0
        self.timeout_count = 0
        self.retry_count = 0
        self.latencies_ms: list[float] = []
        self.start_time = time.monotonic()

    def record_request(
        self,
        *,
        payload_bytes: int = 1024,
        is_retry: bool = False,
        timed_out: bool = False,
        error: str | None = None,
        custom_latency_ms: float | None = None,
    ) -> dict[str, Any]:
        """Record an outgoing request sample under simulated network throttling."""
        if is_retry:
            self.retry_count += 1
        if timed_out:
            self.timeout_count += 1

        # Check if packet is dropped by simulated network
        dropped = is_packet_dropped(self.profile)
        if dropped:
            self.dropped_count += 1

        # Calculate simulated latency
        if custom_latency_ms is not None:
            delay_ms = float(custom_latency_ms)
        else:
            delay_s = calculate_network_transmission_delay(self.profile, payload_bytes)
            delay_ms = 99999.0 if delay_s == float("inf") else delay_s * 1000.0

        self.latencies_ms.append(delay_ms)
        sample = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload_bytes": payload_bytes,
            "latency_ms": round(delay_ms, 2),
            "dropped": dropped,
            "is_retry": is_retry,
            "timed_out": timed_out,
            "error": error,
        }
        self.requests.append(sample)
        return sample

    def compute_summary(self) -> dict[str, Any]:
        """Compute aggregate network performance metrics and application resilience score."""
        total = len(self.requests)
        if total == 0:
            return {
                "profile_id": self.profile_id,
                "profile_name": self.profile.get("name", self.profile_id),
                "total_requests": 0,
                "success_rate": 100.0,
                "resilience_score": 100.0,
                "dropped_packets": 0,
                "timeouts": 0,
                "retries": 0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "max_latency_ms": 0.0,
            }

        valid_latencies = [l for l in self.latencies_ms if l < 90000.0]
        avg_lat = round(sum(valid_latencies) / len(valid_latencies), 2) if valid_latencies else 0.0
        max_lat = round(max(valid_latencies), 2) if valid_latencies else 0.0

        sorted_lat = sorted(valid_latencies)
        p95_idx = int(len(sorted_lat) * 0.95)
        p95_lat = round(sorted_lat[min(p95_idx, len(sorted_lat) - 1)], 2) if sorted_lat else 0.0

        failed_requests = sum(1 for r in self.requests if r.get("dropped") or r.get("timed_out") or r.get("error"))
        success_rate = round(((total - failed_requests) / total) * 100.0, 2)

        # Resilience score: penalized by packet drops, timeouts, and excessive retries
        drop_penalty = (self.dropped_count / total) * 40.0
        timeout_penalty = (self.timeout_count / total) * 40.0
        retry_penalty = min(20.0, (self.retry_count / total) * 20.0)
        resilience = max(0.0, round(100.0 - drop_penalty - timeout_penalty - retry_penalty, 2))

        duration_s = round(time.monotonic() - self.start_time, 2)

        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile.get("name", self.profile_id),
            "duration_seconds": duration_s,
            "total_requests": total,
            "failed_requests": failed_requests,
            "success_rate": success_rate,
            "resilience_score": resilience,
            "dropped_packets": self.dropped_count,
            "timeouts": self.timeout_count,
            "retries": self.retry_count,
            "avg_latency_ms": avg_lat,
            "p95_latency_ms": p95_lat,
            "max_latency_ms": max_lat,
        }


def build_network_run_configuration(
    profile_id: str,
    custom_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate runner-compatible network configuration payload for Web CDP and Android ADB."""
    presets = get_preset_network_profiles()
    profile = custom_profile or presets.get(profile_id) or presets["2g_edge"]

    cdp_params = generate_cdp_network_conditions(profile)
    adb_commands = generate_adb_network_commands(profile)

    return {
        "profile_id": profile_id,
        "profile_name": profile.get("name", profile_id),
        "offline": bool(profile.get("offline", False)),
        "cdp_conditions": cdp_params,
        "adb_setup_commands": adb_commands,
        "adb_teardown_commands": [
            ["svc", "data", "enable"],
            ["svc", "wifi", "enable"],
            ["tc", "qdisc", "del", "dev", "wlan0", "root"],
        ],
    }
