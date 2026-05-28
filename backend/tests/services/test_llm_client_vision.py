import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ai_case.llm_client import LLMRequest


def test_llm_request_accepts_optional_image_fields():
    req = LLMRequest(
        provider="openai",
        api_key="sk",
        model_name="gpt-4o",
        prompt="diagnose",
        image_base64="abc",
        image_media_type="image/png",
    )

    assert req.image_base64 == "abc"
    assert req.image_media_type == "image/png"
