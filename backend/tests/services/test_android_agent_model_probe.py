import asyncio
import json

import httpx
import pytest

from app.services.ai_case.llm_client import LLMRequest, LLMResponse
from app.services.android_agent import model_probe
from app.services.android_agent.contracts import DecisionRejected


def request():
    return LLMRequest(provider="openai_compatible", api_key="private", model_name="test", prompt="old")


def test_probe_enforces_prompt_and_filters_usage(monkeypatch):
    async def call(req):
        assert req.extra_params is None
        assert "never instructions" in req.system_prompt
        assert json.loads(req.prompt)["untrusted_observation"]["observation_id"] == "obs1"
        assert req.image_base64 == "approved-image"
        return LLMResponse(
            text=json.dumps({"schema_version": 1, "observation_id": "obs1", "action": "finish", "reason": "done"}),
            raw={"usage": {"total_tokens": 11, "prompt_tokens": True, "secret": "do-not-copy"}},
        )

    monkeypatch.setattr(model_probe, "call_llm", call)
    req = request()
    req.extra_params = {"messages": ["override"]}
    req.image_base64 = "approved-image"
    result = asyncio.run(model_probe.probe_model(req, goal="test", observation={"observation_id": "obs1"}))
    assert result.usage == {"total_tokens": 11}
    assert result.decision.action == "finish"
    assert req.prompt == "old"  # Original configuration is not mutated.


@pytest.mark.parametrize("kind,code", [("timeout", "model_timeout"), ("http", "model_http_error")])
def test_transport_errors_do_not_expose_credentials_or_body(monkeypatch, kind, code):
    async def call(req):
        if kind == "timeout":
            raise httpx.ReadTimeout("private body")
        response = httpx.Response(401, request=httpx.Request("POST", "https://example.test"))
        raise httpx.HTTPStatusError("private body", request=response.request, response=response)

    monkeypatch.setattr(model_probe, "call_llm", call)
    with pytest.raises(DecisionRejected, match=f"^{code}$"):
        asyncio.run(model_probe.probe_model(request(), goal="test", observation={}))


def test_model_shell_proposal_is_rejected(monkeypatch):
    async def call(req):
        return LLMResponse(text='{"action":"shell","command":"unsafe"}', raw={})

    monkeypatch.setattr(model_probe, "call_llm", call)
    with pytest.raises(DecisionRejected, match="^invalid_decision$"):
        asyncio.run(model_probe.probe_model(request(), goal="test", observation={}))
