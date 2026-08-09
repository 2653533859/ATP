"""AI 用例生成上下文的脱敏与裁剪测试。"""

from types import SimpleNamespace

from app.services.ai_case.context import build_dataset_context, build_mock_rule_context


def test_dataset_context_redacts_secrets_and_limits_rows():
    dataset = SimpleNamespace(
        id=1,
        name="accounts",
        description="demo",
        format="json",
        validation_policy="hard",
        schema_fields=[
            {"name": "username", "type": "string", "required": True},
            {"name": "password", "type": "string", "required": True},
        ],
        rows=[{"username": f"user-{index}", "password": "real-secret"} for index in range(8)],
    )

    context = build_dataset_context(dataset)

    assert context["row_count"] == 8
    assert len(context["sample_rows"]) == 5
    assert context["sample_rows"][0]["password"] == "[已脱敏]"


def test_mock_context_redacts_response_and_recorded_secret_fields():
    rule = SimpleNamespace(
        id=2,
        name="login",
        method="POST",
        path="/login",
        status_code=200,
        response_headers={"Set-Cookie": "session=secret"},
        response_body='{"token":"secret-token","user":"demo"}',
        match_conditions={"headers": {"Authorization": "Bearer secret"}},
        delay_ms=0,
        recorded_samples=[{"request": {"headers": {"Cookie": "sid=secret"}}} for _ in range(5)],
    )

    context = build_mock_rule_context(rule)

    assert context["response_body"]["token"] == "[已脱敏]"
    assert context["response_body"]["user"] == "demo"
    assert context["response_headers"]["Set-Cookie"] == "[已脱敏]"
    assert context["match_conditions"]["headers"]["Authorization"] == "[已脱敏]"
    assert len(context["recorded_samples"]) == 3
