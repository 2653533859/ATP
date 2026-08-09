import pytest

from app.services.web_matrix import WebMatrixError, build_web_matrix


def test_web_matrix_deduplicates_and_normalizes_variants():
    result = build_web_matrix(
        {
            "browser_matrix": [
                {"browser": "chromium", "viewport": {"width": 1280, "height": 720}},
                {"browser": "chromium", "viewport": {"width": 1280, "height": 720}},
                {"browser": "webkit", "viewport": {"width": 390, "height": 844}, "device": "iPhone 14"},
            ]
        }
    )

    assert len(result) == 2
    assert result[1]["browser"] == "webkit"
    assert result[1]["viewport"] == {"width": 390, "height": 844}


@pytest.mark.parametrize("config", [{"browser_matrix": []}, {"browser_matrix": [{"browser": "edge"}]}])
def test_web_matrix_rejects_invalid_configuration(config):
    with pytest.raises(WebMatrixError):
        build_web_matrix(config)
