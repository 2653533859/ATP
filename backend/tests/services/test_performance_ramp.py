import pytest

from app.services.performance_ramp import PerformanceRampError, expand_auto_ramp


def test_expand_auto_ramp_builds_auditable_stages():
    result = expand_auto_ramp(
        {"auto_ramp": {"start_vus": 10, "step_vus": 10, "max_vus": 30, "ramp_duration": "5s", "hold_duration": "10s"}}
    )

    assert result["stages"] == [
        {"duration": "5s", "target": 10},
        {"duration": "5s", "target": 20},
        {"duration": "10s", "target": 30},
    ]
    assert result["auto_ramp"]["generated_stage_count"] == 3


@pytest.mark.parametrize(
    "config",
    [
        {"auto_ramp": {"start_vus": 0}},
        {"auto_ramp": {"start_vus": 10, "step_vus": 0, "max_vus": 20}},
        {"auto_ramp": {"max_vus": float("inf")}},
        {"auto_ramp": "invalid"},
    ],
)
def test_expand_auto_ramp_rejects_unsafe_values(config):
    with pytest.raises(PerformanceRampError):
        expand_auto_ramp(config)
