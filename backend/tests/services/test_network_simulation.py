"""Unit tests for Q1.1 Mobile Network Simulation and Bandwidth/Loss Throttling.

Tests:
1. get_preset_network_profiles lists standard preset profiles
2. calculate_network_transmission_delay computes bandwidth transfer delay and jitter
3. is_packet_dropped checks packet loss probability and offline state
4. generate_cdp_network_conditions formats CDP Network.emulateNetworkConditions
5. generate_adb_network_commands generates Android ADB interface toggles and netem rules
"""

from __future__ import annotations


from app.models.bootstrap import load_all_models
from app.services.network_simulation import (
    calculate_network_transmission_delay,
    generate_adb_network_commands,
    generate_cdp_network_conditions,
    get_preset_network_profiles,
    is_packet_dropped,
)

load_all_models()


def test_preset_network_profiles_coverage():
    presets = get_preset_network_profiles()
    assert "offline" in presets
    assert "2g_gprs" in presets
    assert "2g_edge" in presets
    assert "3g_hspa" in presets
    assert "4g_lte" in presets
    assert "high_packet_loss" in presets

    for _pid, profile in presets.items():
        assert "latency_ms" in profile
        assert "download_kbps" in profile
        assert "upload_kbps" in profile
        assert "packet_loss_percent" in profile


def test_calculate_transmission_delay_bandwidth_and_latency():
    presets = get_preset_network_profiles()

    # 1. Offline profile gives infinity
    assert calculate_network_transmission_delay(presets["offline"]) == float("inf")

    # 2. 4G LTE with small payload: mostly base latency (~30ms)
    delay_4g = calculate_network_transmission_delay(presets["4g_lte"], payload_bytes=0, seed=42)
    assert 0.025 <= delay_4g <= 0.035

    # 3. 2G GPRS (50 kbps, 500ms latency) with 10KB payload
    # 10240 * 8 / (50 * 1000) = 1.6384s transmission + 0.5s base latency = ~2.1384s
    delay_2g = calculate_network_transmission_delay(presets["2g_gprs"], payload_bytes=10240, seed=42)
    assert 2.0 <= delay_2g <= 2.3


def test_is_packet_dropped_verdict():
    presets = get_preset_network_profiles()

    # Offline -> 100% dropped
    assert is_packet_dropped(presets["offline"]) is True

    # 4G LTE (0% loss) -> never dropped
    assert is_packet_dropped(presets["4g_lte"], seed=0.5) is False

    # High packet loss (15% loss)
    # With seed producing uniform 10.0 -> dropped (< 15)
    assert is_packet_dropped(presets["high_packet_loss"], seed=1) is True
    # With 100% loss custom profile
    assert is_packet_dropped({"packet_loss_percent": 100.0}) is True


def test_generate_cdp_network_conditions():
    presets = get_preset_network_profiles()
    cdp_2g = generate_cdp_network_conditions(presets["2g_edge"])
    assert cdp_2g["offline"] is False
    assert cdp_2g["latency"] == 300
    assert cdp_2g["downloadThroughput"] > 0
    assert cdp_2g["uploadThroughput"] > 0

    cdp_offline = generate_cdp_network_conditions(presets["offline"])
    assert cdp_offline["offline"] is True
    assert cdp_offline["downloadThroughput"] == -1


def test_generate_adb_network_commands():
    presets = get_preset_network_profiles()

    # Offline disables data and wifi interfaces
    adb_offline = generate_adb_network_commands(presets["offline"])
    assert ["svc", "data", "disable"] in adb_offline
    assert ["svc", "wifi", "disable"] in adb_offline

    # 2G GPRS enables interfaces and applies tc netem delay rule
    adb_2g = generate_adb_network_commands(presets["2g_gprs"])
    assert ["svc", "data", "enable"] in adb_2g
    assert any("netem" in cmd and "delay" in cmd for cmd in adb_2g)
