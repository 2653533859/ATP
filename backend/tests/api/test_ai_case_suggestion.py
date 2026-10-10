import asyncio
from types import SimpleNamespace
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import ai_case_generation
from app.models.user import User
from app.schemas.ai_case import AIAssertionSuggestIn
from app.services.ai_case.suggestion import heuristic_suggestions


class _Result:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def scalars(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class _DB:
    def __init__(self, llm_config=None, project=None):
        self.llm_config = llm_config
        self.project = project

    async def get(self, model, entity_id):
        if getattr(model, "__name__", "") == "Project" and self.project and entity_id == self.project.id:
            return self.project
        if getattr(model, "__name__", "") == "AILLMConfig" and self.llm_config and entity_id == self.llm_config.id:
            return self.llm_config
        return None

    async def execute(self, _statement):
        return _Result([self.llm_config] if self.llm_config else [])


def _engineer() -> User:
    return cast(User, SimpleNamespace(id=1, username="test_qa", role="engineer"))


def test_heuristic_suggestions_extracts_tokens_ids_and_codes():
    sample_response = {
        "code": 0,
        "message": "success",
        "data": {
            "token": "eyJhbGciOi...",
            "user_id": 10086,
            "roles": ["admin", "tester"],
        },
    }

    assertions, extractions = heuristic_suggestions(
        method="POST",
        url="/api/v1/login",
        status_code=200,
        response_body=sample_response,
    )

    # 1. Assertions verification
    targets = [a.target for a in assertions]
    assert "status_code" in targets
    assert any(a.expression == "$.code" and a.expected == "0" for a in assertions)
    assert any(a.expression == "$.message" and "success" in a.expected for a in assertions)
    assert any("token" in a.expression for a in assertions)
    assert any("user_id" in a.expression for a in assertions)

    # 2. Extractions verification
    vars_extracted = {e.variable: e.expression for e in extractions}
    assert "token" in vars_extracted
    assert vars_extracted["token"] == "$.data.token"
    assert "user_id" in vars_extracted
    assert vars_extracted["user_id"] == "$.data.user_id"


def test_suggest_assertions_endpoint_returns_heuristic():
    db = cast(AsyncSession, _DB(llm_config=None))
    req = AIAssertionSuggestIn(
        method="POST",
        url="/api/v1/orders",
        status_code=201,
        response_body={"code": 200, "data": {"order_id": 999}},
    )

    out = asyncio.run(ai_case_generation.suggest_assertions_endpoint(req, db, _engineer()))
    assert out.source == "heuristic"
    assert any(a.target == "status_code" and a.expected == "201" for a in out.assertions)
    assert any(e.variable == "order_id" for e in out.extractions)
