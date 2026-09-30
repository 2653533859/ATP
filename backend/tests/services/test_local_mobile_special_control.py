"""Android cancellation stays local when the SQLite profile is active."""

from app.services import mobile_special_control


def test_local_android_cancel_signal_does_not_use_redis(monkeypatch) -> None:
    monkeypatch.setattr(mobile_special_control.settings, "ATP_LOCAL_MODE", True)
    monkeypatch.setattr(
        mobile_special_control,
        "create_redis_control_client",
        lambda: (_ for _ in ()).throw(AssertionError("Redis must not be used")),
    )
    run_id = 812345
    mobile_special_control.clear_cancel_request(run_id)
    assert not mobile_special_control.is_cancel_requested(run_id)
    mobile_special_control.request_cancel(run_id)
    assert mobile_special_control.is_cancel_requested(run_id)
    mobile_special_control.clear_cancel_request(run_id)
    assert not mobile_special_control.is_cancel_requested(run_id)
