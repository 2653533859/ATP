import pytest

from app.services.mobile_special import preflight


@pytest.mark.asyncio
async def test_android_preflight_applies_opt_in_actions(monkeypatch):
    calls = []

    def fake_run(serial, args, **kwargs):
        calls.append((serial, args))
        return type("Proc", (), {"returncode": 0, "stdout": "Success", "stderr": ""})()

    monkeypatch.setattr(preflight, "safe_run_adb", fake_run)

    result = await preflight.run_android_preflight(
        serial="emulator-5554",
        package="com.example.app",
        config={"uninstall_before": True, "clear_data_before": True, "launch_before": True},
    )

    assert result["actions"] == ["uninstall_before", "clear_data_before", "launch_before"]
    assert calls == [
        ("emulator-5554", ["shell", "pm", "uninstall", "com.example.app"]),
        ("emulator-5554", ["shell", "pm", "clear", "com.example.app"]),
        (
            "emulator-5554",
            ["shell", "monkey", "-p", "com.example.app", "-c", "android.intent.category.LAUNCHER", "1"],
        ),
    ]


@pytest.mark.asyncio
async def test_android_preflight_uses_explicit_activity_when_provided(monkeypatch):
    calls = []

    def fake_run(serial, args, **kwargs):
        calls.append((serial, args))
        return type("Proc", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(preflight, "safe_run_adb", fake_run)

    await preflight.run_android_preflight(
        serial="emulator-5554",
        package="com.example.app",
        config={"launch_before": True, "launch_activity": ".WelcomeActivity"},
    )

    assert calls == [("emulator-5554", ["shell", "am", "start", "-n", "com.example.app/.WelcomeActivity"])]


@pytest.mark.asyncio
async def test_install_requires_an_apk_asset():
    with pytest.raises(preflight.AndroidPreflightError, match="没有绑定 APK"):
        await preflight.run_android_preflight(
            serial="emulator-5554",
            package="com.example.app",
            config={"install_apk": True},
        )
