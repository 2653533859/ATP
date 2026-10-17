"""探索过程异常侦测器单测 (T2.2)"""

from __future__ import annotations

import pytest

from app.services.exploration_anomaly_detector import (
    AnomalySeverity,
    AnomalyType,
    clear_anomaly_records,
    inspect_screen_anomaly,
    list_anomaly_records,
)
from app.services.vlm_autonomous_explorer import (
    DetectedUIElement,
    start_exploration_session,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_anomaly_records()
    yield
    clear_anomaly_records()


def test_anomaly_detection_white_screen_and_deadlock():
    sess = start_exploration_session(platform="web", device_id="chrome_1")

    # 1. 元素为 0 触发白屏异常
    anom_white = inspect_screen_anomaly(
        session=sess,
        screenshot_b64="valid_img_base64_string",
        elements=[],
    )
    assert anom_white is not None
    assert anom_white.anomaly_type == AnomalyType.WHITE_SCREEN
    assert anom_white.severity == AnomalySeverity.CRITICAL

    # 2. 连续 4 次相同状态触发死锁异常
    dummy_elements = [
        DetectedUIElement("el_1", "button", "刷新页面", [10, 10, 100, 40]),
    ]
    anom_deadlock = inspect_screen_anomaly(
        session=sess,
        screenshot_b64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        elements=dummy_elements,
        consecutive_same_state_count=4,
    )
    assert anom_deadlock is not None
    assert anom_deadlock.anomaly_type == AnomalyType.STATE_DEADLOCK

    # 3. 错误弹窗异常
    error_elements = [
        DetectedUIElement("el_err", "button", "网络错误 500 无法连接", [50, 50, 200, 100]),
    ]
    anom_dialog = inspect_screen_anomaly(
        session=sess,
        screenshot_b64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        elements=error_elements,
    )
    assert anom_dialog is not None
    assert anom_dialog.anomaly_type == AnomalyType.ERROR_DIALOG

    assert len(list_anomaly_records(session_id=sess.session_id)) == 3
