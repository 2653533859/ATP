import pytest

from app.services.dataset_execution import (
    DatasetExecutionError,
    build_dataset_iterations,
    redact_dataset_row,
    redact_execution_evidence,
)


def test_sequential_strategy_preserves_legacy_order():
    rows = [{"id": 1}, {"id": 2}]

    assert build_dataset_iterations(rows) == rows
    assert build_dataset_iterations(rows, fixed_count=1) == [{"id": 1}]


def test_random_strategy_is_seeded_and_bounded():
    rows = [{"id": index} for index in range(5)]

    first = build_dataset_iterations(rows, strategy="random", fixed_count=3, seed=7)
    second = build_dataset_iterations(rows, strategy="random", fixed_count=3, seed=7)

    assert first == second
    assert len(first) == 3
    assert {row["id"] for row in first} <= set(range(5))


def test_fixed_count_cycles_rows():
    assert build_dataset_iterations([{"id": 1}, {"id": 2}], strategy="fixed_count", fixed_count=5) == [
        {"id": 1},
        {"id": 2},
        {"id": 1},
        {"id": 2},
        {"id": 1},
    ]


def test_cartesian_strategy_builds_controlled_combinations():
    rows = [{"browser": ["chromium", "firefox"], "locale": ["zh", "en"], "base_url": "https://test"}]

    result = build_dataset_iterations(rows, strategy="cartesian", combination_fields=["browser", "locale"])

    assert len(result) == 4
    assert {item["browser"] for item in result} == {"chromium", "firefox"}
    assert {item["locale"] for item in result} == {"zh", "en"}
    assert all(item["base_url"] == "https://test" for item in result)


def test_pairwise_strategy_covers_each_value_pair_and_redacts_persisted_fields():
    rows = [{"browser": ["chromium", "firefox"], "locale": ["zh", "en"], "device": ["desktop", "mobile"]}]

    result = build_dataset_iterations(
        rows, strategy="pairwise", combination_fields=["browser", "locale", "device"], seed=3
    )
    pairs = {(item["browser"], item["locale"]) for item in result}

    assert pairs == {("chromium", "zh"), ("chromium", "en"), ("firefox", "zh"), ("firefox", "en")}
    source = {"token": "secret", "user": {"password": "p"}}
    assert redact_dataset_row(source, ["token", "user.password"]) == {
        "token": "***",
        "user": {"password": "***"},
    }
    assert source == {"token": "secret", "user": {"password": "p"}}


def test_execution_evidence_redaction_searches_nested_request_and_response_data():
    evidence = {
        "request": {"headers": {"Authorization": "secret"}, "body": {"token": "request-secret"}},
        "response": [{"user": {"password": "response-secret"}}],
    }

    redacted = redact_execution_evidence(evidence, ["authorization", "token", "user.password"])

    assert redacted["request"]["headers"]["Authorization"] == "***"
    assert redacted["request"]["body"]["token"] == "***"
    assert redacted["response"][0]["user"]["password"] == "***"
    assert evidence["request"]["body"]["token"] == "request-secret"


def test_combination_strategy_rejects_large_product_before_materializing_rows():
    with pytest.raises(DatasetExecutionError, match="组合数量超过上限"):
        build_dataset_iterations(
            [{"browser": list(range(100)), "locale": list(range(100))}],
            strategy="cartesian",
            combination_fields=["browser", "locale"],
            max_iterations=10,
        )


def test_max_iterations_accepts_numeric_strings_and_rejects_invalid_values():
    assert len(build_dataset_iterations([{"id": 1}], fixed_count=2, strategy="fixed_count", max_iterations="2")) == 2
    with pytest.raises(DatasetExecutionError):
        build_dataset_iterations([{"id": 1}], max_iterations="not-a-number")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"strategy": "unknown"},
        {"strategy": "fixed_count"},
        {"strategy": "sequential", "fixed_count": 3},
        {"strategy": "fixed_count", "fixed_count": 1001},
    ],
)
def test_invalid_or_unsafe_strategy_is_rejected(kwargs):
    with pytest.raises(DatasetExecutionError):
        build_dataset_iterations([{"id": 1}, {"id": 2}], **kwargs)
