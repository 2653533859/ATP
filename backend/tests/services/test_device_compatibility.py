import pytest

from app.services.device_compatibility import DeviceCompatibilityError, build_android_device_matrix


def test_device_matrix_normalizes_registered_device_metadata():
    result = build_android_device_matrix(
        [{"serial": "emulator-1", "os_version": "14"}],
        available_devices=[
            {
                "serial": "emulator-1",
                "id": 41,
                "model": "Pixel 8",
                "brand": "Google",
                "os_version": "14",
                "resolution": "1080x2400",
            }
        ],
    )

    assert result == [
        {
            "serial": "emulator-1",
            "device_id": 41,
            "model": "Pixel 8",
            "brand": "Google",
            "os_version": "14",
            "resolution": "1080x2400",
        }
    ]


@pytest.mark.parametrize(
    "requested, available, expected",
    [
        ([{"serial": "missing"}], [{"serial": "known"}], "设备未注册"),
        (
            [{"serial": "known", "resolution": "720x1280"}],
            [{"serial": "known", "resolution": "1080x1920"}],
            "resolution 不匹配",
        ),
        ([{"serial": "known"}, {"serial": "known"}], [], "重复设备"),
    ],
)
def test_device_matrix_rejects_invalid_or_incompatible_variants(requested, available, expected):
    with pytest.raises(DeviceCompatibilityError, match=expected):
        build_android_device_matrix(requested, available_devices=available)
