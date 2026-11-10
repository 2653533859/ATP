"""Tests for multimodal Observation model, validation helpers and device adapter safety."""

from datetime import datetime, timezone
import pytest

from app.services.android_agent.device_adapter import AndroidDeviceAdapter, DeviceAdapterError
from app.services.android_agent.observation import (
    Observation,
    ObservationRejected,
    ScreenMetrics,
    UiNode,
    build_model_observation,
    check_page_consistency,
    compute_bytes_hash,
    detect_secure_window,
    validate_observation_skew,
)


def test_screen_metrics_bounds():
    metrics = ScreenMetrics(width=1080, height=2400, rotation=0)
    assert metrics.width == 1080
    assert metrics.rotation == 0

    with pytest.raises(ObservationRejected, match="invalid_screen_size"):
        ScreenMetrics(width=-1, height=2400)

    with pytest.raises(ObservationRejected, match="invalid_screen_rotation"):
        ScreenMetrics(width=1080, height=2400, rotation=45)


def test_observation_and_build_model_observation():
    node1 = UiNode(
        node_id="n1",
        parent_id=None,
        resource_id="com.shop:id/title",
        text="Shoes",
        content_desc="",
        class_name="android.widget.TextView",
        bounds=(10, 10, 200, 50),
        enabled=True,
        clickable=True,
        redacted=False,
    )
    node_pwd = UiNode(
        node_id="n2",
        parent_id=None,
        resource_id="com.shop:id/pwd",
        text="",
        content_desc="",
        class_name="android.widget.EditText",
        bounds=(10, 60, 200, 100),
        enabled=True,
        clickable=True,
        redacted=True,
    )

    obs = Observation(
        observation_id="obs-1",
        session_id=1,
        captured_at=datetime.now(timezone.utc),
        package_name="com.shop",
        activity="com.shop.MainActivity",
        screen=ScreenMetrics(width=1080, height=2400),
        screenshot_path="projects/1/sessions/1/obs-1.jpg",
        screenshot_hash="mock_hash",
        nodes=[node1, node_pwd],
        capture_skew_ms=120,
    )

    context = build_model_observation(obs, allowed_value_refs=["item_name", "category"])
    assert context["observation_id"] == "obs-1"
    assert context["package_name"] == "com.shop"
    assert context["allowed_value_refs"] == ["category", "item_name"]
    # 敏感节点必须被过滤掉，不发送给 LLM
    assert len(context["nodes"]) == 1
    assert context["nodes"][0]["node_id"] == "n1"


def test_validate_observation_skew():
    validate_observation_skew(100)
    validate_observation_skew(1500, max_skew_ms=2000)

    with pytest.raises(ObservationRejected, match="capture_skew_too_high"):
        validate_observation_skew(2500, max_skew_ms=2000)

    with pytest.raises(ObservationRejected, match="capture_skew_too_high"):
        validate_observation_skew(-10)


def test_check_page_consistency():
    check_page_consistency("com.shop", "com.shop", "com.shop")

    with pytest.raises(ObservationRejected, match="unexpected_package"):
        # 抓取过程中切出了桌面
        check_page_consistency("com.shop", "com.android.launcher", "com.shop")

    with pytest.raises(ObservationRejected, match="unexpected_package"):
        # 初始不在目标包
        check_page_consistency("com.other", "com.other", "com.shop")


def test_detect_secure_window():
    # 纯 0 字节模拟 FLAG_SECURE 黑屏
    blank_data = b"\x00" * 2048
    assert detect_secure_window(blank_data) is True

    # 包含图像有效负载
    real_data = b"\x89PNG\r\n\x1a\n" + b"\x12\x34\x56\x78" * 500
    assert detect_secure_window(real_data) is False

    assert len(compute_bytes_hash(real_data)) == 64


class FakeTransport:
    def __init__(self, package="com.shop"):
        self.pkg = package
        self.calls = []

    def current_package(self):
        return self.pkg

    def rpc_once(self, method, params):
        self.calls.append((method, params))
        return True


def test_adapter_swipe_safety():
    transport = FakeTransport()
    adapter = AndroidDeviceAdapter(transport, package="com.shop", width=1080, height=2400)

    gate_checked = []

    def gate():
        gate_checked.append(True)

    # 1. 向上滑动
    adapter.swipe("up", 0.5, assert_write_allowed=gate)
    assert len(gate_checked) == 1
    assert len(transport.calls) == 1
    method, params = transport.calls[0]
    assert method == "swipe"
    sx, sy, ex, ey, steps = params
    assert sx == 540 and ex == 540
    assert sy > ey  # 向上滑动
    assert steps == 50

    # 2. 超限距离必须被拦截
    with pytest.raises(DeviceAdapterError, match="invalid_swipe_distance"):
        adapter.swipe("up", 0.95, assert_write_allowed=gate)

    # 3. 非法方向
    with pytest.raises(DeviceAdapterError, match="invalid_swipe_direction"):
        adapter.swipe("diagonal", 0.5, assert_write_allowed=gate)


def test_adapter_swipe_unknown_outcome_on_exception():
    class BrokenTransport(FakeTransport):
        def rpc_once(self, *args, **kwargs):
            _ = (args, kwargs)
            raise RuntimeError("adb rpc socket closed")

    adapter = AndroidDeviceAdapter(BrokenTransport(), package="com.shop", width=1080, height=2400)
    with pytest.raises(DeviceAdapterError, match="write_outcome_unknown"):
        adapter.swipe("down", 0.4, assert_write_allowed=lambda: None)
