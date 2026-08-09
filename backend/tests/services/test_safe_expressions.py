import pytest

from app.services.safe_expressions import SafeExpressionError, evaluate_safe_expression


def test_safe_expression_reads_nested_data_and_short_circuits():
    context = {
        "status_code": 200,
        "body": {"data": {"items": [{"id": "u-1"}]}},
        "headers": {"x-request-id": "req-1"},
        "response_time_ms": 42,
    }

    assert evaluate_safe_expression("status_code == 200 and body['data']['items'][0]['id'] == 'u-1'", context)
    assert evaluate_safe_expression("headers['x-request-id'] == 'req-1' and response_time_ms < 100", context)


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('whoami')",
        "body.get('data')",
        "body['data'] + 1",
        "body.__class__",
        "missing == 1",
    ],
)
def test_safe_expression_rejects_calls_private_access_and_arithmetic(expression):
    with pytest.raises(SafeExpressionError):
        evaluate_safe_expression(expression, {"body": {"data": 1}})


def test_safe_expression_rejects_excessive_length_and_complexity():
    with pytest.raises(SafeExpressionError):
        evaluate_safe_expression("a == 1 " * 100, {"a": 1})

    with pytest.raises(SafeExpressionError):
        evaluate_safe_expression("a == " + "[" * 80 + "1" + "]" * 80, {"a": 1})
