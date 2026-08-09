"""Build deterministic, bounded dataset iterations for case execution."""

from __future__ import annotations

import itertools
import random
from copy import deepcopy
from collections.abc import Iterable, Sequence
from typing import Any


class DatasetExecutionError(ValueError):
    """Raised when a dataset iteration strategy is invalid."""


SUPPORTED_DATASET_STRATEGIES = {"sequential", "random", "fixed_count", "cartesian", "pairwise"}
DEFAULT_MAX_ITERATIONS = 1000
DEFAULT_REDACTED_VALUE = "***"


def build_dataset_iterations(
    rows: Sequence[Any],
    *,
    strategy: str = "sequential",
    fixed_count: int | None = None,
    seed: int | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    combination_fields: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Return bounded row inputs according to a case's dataset strategy.

    ``sequential`` preserves the existing behavior. ``random`` shuffles the
    complete dataset (or samples a requested count), while ``fixed_count``
    cycles through rows until the requested count is reached. ``cartesian``
    creates every combination of the selected field values and ``pairwise``
    creates a bounded set covering every pair of selected values. A local RNG
    and an optional seed make retries reproducible without mutating global state.
    """

    normalized_strategy = str(strategy or "sequential").strip().lower()
    if normalized_strategy not in SUPPORTED_DATASET_STRATEGIES:
        supported = ", ".join(sorted(SUPPORTED_DATASET_STRATEGIES))
        raise DatasetExecutionError(f"不支持的数据集执行策略: {normalized_strategy}，可选: {supported}")
    try:
        normalized_max_iterations = int(max_iterations)
    except (TypeError, ValueError) as exc:
        raise DatasetExecutionError("数据集最大执行次数必须是整数") from exc
    if normalized_max_iterations < 1:
        raise DatasetExecutionError("数据集最大执行次数必须大于 0")

    normalized_rows = [dict(row) if isinstance(row, dict) else {"value": row} for row in rows]
    if not normalized_rows:
        return []

    if normalized_strategy in {"cartesian", "pairwise"}:
        combinations = _build_combinations(
            normalized_rows,
            fields=combination_fields,
            strategy=normalized_strategy,
            seed=seed,
            max_iterations=normalized_max_iterations,
        )
        if fixed_count is not None:
            if int(fixed_count) < 1:
                raise DatasetExecutionError("fixed_count 必须大于 0")
            if int(fixed_count) > len(combinations):
                raise DatasetExecutionError("受控组合的 fixed_count 不能超过组合总数")
            combinations = combinations[: int(fixed_count)]
        return combinations

    count = len(normalized_rows)
    if normalized_strategy == "fixed_count":
        if fixed_count is None or int(fixed_count) < 1:
            raise DatasetExecutionError("fixed_count 策略必须提供大于 0 的 fixed_count")
        count = int(fixed_count)
    elif fixed_count is not None:
        count = int(fixed_count)
        if count < 1:
            raise DatasetExecutionError("fixed_count 必须大于 0")

    if count > normalized_max_iterations:
        raise DatasetExecutionError(f"数据集执行次数不能超过 {normalized_max_iterations}")

    rng = random.Random(seed)
    if normalized_strategy == "sequential":
        if count > len(normalized_rows):
            raise DatasetExecutionError("顺序策略的 fixed_count 不能超过数据集行数")
        return normalized_rows[:count]
    if normalized_strategy == "random":
        if count <= len(normalized_rows):
            return rng.sample(normalized_rows, count)
        shuffled = list(normalized_rows)
        rng.shuffle(shuffled)
        return [shuffled[index % len(shuffled)] for index in range(count)]

    return [normalized_rows[index % len(normalized_rows)] for index in range(count)]


def redact_dataset_row(
    row: dict[str, Any],
    fields: Iterable[str] | None = None,
    *,
    replacement: str = DEFAULT_REDACTED_VALUE,
) -> dict[str, Any]:
    """Return a persisted-safe copy of a dataset row.

    Redaction is explicit: only configured fields are masked, while the
    original row remains available to the executor in memory. Nested values
    are supported with dotted paths such as ``user.token``.
    """

    result = deepcopy(row)
    for field in {str(item).strip() for item in (fields or []) if str(item).strip()}:
        _redact_path(result, field.split("."), replacement)
    return result


def redact_execution_evidence(
    value: Any,
    fields: Iterable[str] | None = None,
    *,
    replacement: str = DEFAULT_REDACTED_VALUE,
) -> Any:
    """Return a redacted copy of nested execution evidence."""

    result = deepcopy(value)
    for field in {str(item).strip() for item in (fields or []) if str(item).strip()}:
        _redact_nested_paths(result, field.split("."), replacement)
    return result


def _redact_nested_paths(value: Any, path: list[str], replacement: str) -> None:
    if not path:
        return
    if isinstance(value, dict):
        for key, child in list(value.items()):
            if str(key).casefold() == path[0].casefold():
                if len(path) == 1:
                    value[key] = replacement
                else:
                    _redact_nested_paths(child, path[1:], replacement)
            elif isinstance(child, (dict, list)):
                _redact_nested_paths(child, path, replacement)
    elif isinstance(value, list):
        for child in value:
            _redact_nested_paths(child, path, replacement)


def _redact_path(value: Any, path: list[str], replacement: str) -> None:
    if not path or not isinstance(value, dict):
        return
    key = path[0]
    if key not in value:
        return
    if len(path) == 1:
        value[key] = replacement
        return
    _redact_path(value[key], path[1:], replacement)


def _build_combinations(
    rows: list[dict[str, Any]],
    *,
    fields: Sequence[str] | None,
    strategy: str,
    seed: int | None,
    max_iterations: int,
) -> list[dict[str, Any]]:
    normalized_fields = [str(field).strip() for field in (fields or []) if str(field).strip()]
    if not normalized_fields:
        raise DatasetExecutionError("受控组合策略必须提供 combination_fields")

    pools: dict[str, list[Any]] = {}
    for field in normalized_fields:
        values: list[Any] = []
        for row in rows:
            if field not in row:
                continue
            candidate = row[field]
            candidates = candidate if isinstance(candidate, (list, tuple, set)) else [candidate]
            for item in candidates:
                if not any(item == existing for existing in values):
                    values.append(item)
        if not values:
            raise DatasetExecutionError(f"受控组合字段没有可用值: {field}")
        pools[field] = values

    base = {key: value for key, value in rows[0].items() if key not in normalized_fields}
    domains = [pools[field] for field in normalized_fields]
    candidate_count = 1
    for domain in domains:
        candidate_count *= len(domain)
        if candidate_count > max_iterations:
            raise DatasetExecutionError(f"组合数量超过上限 {max_iterations}")
    candidates = [dict(zip(normalized_fields, values, strict=True)) for values in itertools.product(*domains)]

    if strategy == "cartesian":
        return [{**base, **candidate} for candidate in candidates]

    return [{**base, **candidate} for candidate in _pairwise_candidates(normalized_fields, candidates, seed)]


def _pairwise_candidates(
    fields: list[str],
    candidates: list[dict[str, Any]],
    seed: int | None,
) -> list[dict[str, Any]]:
    if len(fields) < 2:
        return candidates[:1]

    required = {
        (left, right, _stable_value(candidate[fields[left]]), _stable_value(candidate[fields[right]]))
        for left in range(len(fields))
        for right in range(left + 1, len(fields))
        for candidate in candidates
    }
    order = list(candidates)
    random.Random(seed).shuffle(order)
    selected: list[dict[str, Any]] = []
    while required and order:
        best = max(
            order,
            key=lambda candidate: sum(
                (left, right, _stable_value(candidate[fields[left]]), _stable_value(candidate[fields[right]]))
                in required
                for left in range(len(fields))
                for right in range(left + 1, len(fields))
            ),
        )
        covered = {
            (left, right, _stable_value(best[fields[left]]), _stable_value(best[fields[right]]))
            for left in range(len(fields))
            for right in range(left + 1, len(fields))
        }
        required.difference_update(covered)
        selected.append(best)
        order.remove(best)
    if required:
        raise DatasetExecutionError("pairwise 组合无法在执行上限内覆盖全部字段对")
    return selected


def _stable_value(value: Any) -> str:
    return repr(value)
