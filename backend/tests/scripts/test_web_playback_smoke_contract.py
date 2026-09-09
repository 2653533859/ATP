"""Static safety and evidence contract checks for Web playback acceptance."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "scripts" / "web-playback-smoke.py"


def test_web_playback_smoke_requires_explicit_scope_and_credentials():
    source = SOURCE.read_text(encoding="utf-8")

    assert 'parser.add_argument("--project-id", type=int, required=True)' in source
    assert 'parser.add_argument("--module-id", type=int, required=True)' in source
    assert 'parser.add_argument("--start-url", required=True)' in source
    assert 'os.getenv("ATP_TOKEN")' in source
    assert 'os.getenv("ATP_PASSWORD")' in source
    assert "password=" not in source


def test_web_playback_smoke_checks_all_browsers_assets_and_evidence():
    source = SOURCE.read_text(encoding="utf-8")

    for browser in ("chromium", "firefox", "webkit"):
        assert f'"browser": "{browser}"' in source
    for action in ("page_object", "visual_assert"):
        assert f'"action": "{action}"' in source
    for evidence in ("trace_url", "video_url", "screenshot_url", "network_events"):
        assert evidence in source
    assert "_require_visual_evidence(visual)" in source
    assert "finally:" in source
    assert "_redact_url" in source
    assert "return 1" in source
