"""Dynamic Parameter Dependency Extraction and Placeholder Replacement Service (T1.2).

Provides:
1. Cross-step parameter dependency discovery (upstream response to downstream request).
2. Deep extraction of candidate scalars (IDs, UUIDs, tokens) and their JSONPath expressions.
3. Automated placeholder replacement ({{variable}}) in URL paths, query parameters, headers, and request bodies.
4. Dependency linkage graph generation for automated test suite synthesis.
"""

from __future__ import annotations

from copy import deepcopy
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Ignore trivial numbers and short common strings to avoid false positive substitutions
IGNORED_VALUES = {
    0,
    1,
    2,
    200,
    201,
    204,
    400,
    401,
    403,
    404,
    500,
    True,
    False,
    None,
    "",
    "ok",
    "true",
    "false",
    "success",
    "error",
    "null",
}


def _extract_leaf_candidates(
    data: Any,
    current_path: str = "$",
) -> list[tuple[str, Any, str]]:
    """Recursively extract candidate scalar leaf values with their JSONPath and field name.

    Returns:
        List of tuples: (jsonpath, value, field_name)
    """
    candidates: list[tuple[str, Any, str]] = []

    if isinstance(data, dict):
        for k, v in data.items():
            path = f"{current_path}.{k}"
            if isinstance(v, (dict, list)):
                candidates.extend(_extract_leaf_candidates(v, path))
            else:
                # Filter out booleans, trivial numbers, short strings
                if v in IGNORED_VALUES or isinstance(v, bool):
                    continue
                if isinstance(v, str) and len(v.strip()) < 3:
                    continue
                candidates.append((path, v, str(k)))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            path = f"{current_path}[{idx}]"
            candidates.extend(_extract_leaf_candidates(item, path))

    return candidates


def _generate_variable_name(field_name: str, step_index: int, existing_vars: set[str]) -> str:
    """Generate a clean, readable variable name without conflicts."""
    clean_name = re.sub(r"[^a-zA-Z0-9_]", "", field_name.lower())
    if not clean_name or clean_name[0].isdigit():
        clean_name = f"var_{clean_name}"

    candidate = clean_name
    counter = 1
    while candidate in existing_vars:
        candidate = f"{clean_name}_{step_index + 1}_{counter}"
        counter += 1

    existing_vars.add(candidate)
    return candidate


def _replace_in_object(obj: Any, raw_val_str: str, placeholder: str) -> tuple[Any, bool]:
    """Recursively replace occurrences of raw_val_str with placeholder in JSON structures."""
    replaced = False

    if isinstance(obj, dict):
        new_dict: dict[str, Any] = {}
        for k, v in obj.items():
            new_v, r = _replace_in_object(v, raw_val_str, placeholder)
            new_dict[k] = new_v
            if r:
                replaced = True
        return new_dict, replaced
    elif isinstance(obj, list):
        new_list: list[Any] = []
        for item in obj:
            new_item, r = _replace_in_object(item, raw_val_str, placeholder)
            new_list.append(new_item)
            if r:
                replaced = True
        return new_list, replaced
    elif isinstance(obj, (int, float)):
        # Exact number match
        if str(obj) == raw_val_str:
            return placeholder, True
        return obj, False
    elif isinstance(obj, str):
        if raw_val_str in obj:
            return obj.replace(raw_val_str, placeholder), True
        return obj, False
    else:
        return obj, False


def extract_and_parameterize_traffic_stream(
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze an ordered list of clean traffic entries and extract dynamic parameter dependencies.

    Args:
        entries: Ordered list of clean traffic entries from TrafficRecordingSession.

    Returns:
        Dict with parameterized_entries, discovered_dependencies, and dependency graph.
    """
    if not entries:
        return {
            "parameterized_entries": [],
            "discovered_dependencies": [],
            "total_dependencies_count": 0,
        }

    parameterized = deepcopy(entries)
    dependencies: list[dict[str, Any]] = []
    known_variables: set[str] = set()

    # Step-by-step sequential analysis
    for i in range(len(parameterized)):
        prod_entry = parameterized[i]
        resp_body = prod_entry.get("response_body")
        if not resp_body:
            continue

        # Extract candidates from upstream response body
        candidates = _extract_leaf_candidates(resp_body)
        extractions = prod_entry.setdefault("extractions", [])

        for jsonpath, value, field_name in candidates:
            val_str = str(value)
            if len(val_str) < 3 or val_str in IGNORED_VALUES:
                continue

            var_name: str | None = None
            extracted_for_step = False

            # Check all downstream requests j > i
            for j in range(i + 1, len(parameterized)):
                consumer = parameterized[j]
                consumer_matched = False

                # 1. Match in URL Path
                curr_path = consumer.get("path", "")
                if val_str in curr_path:
                    if var_name is None:
                        var_name = _generate_variable_name(field_name, i, known_variables)
                    placeholder = f"{{{{{var_name}}}}}"
                    consumer["path"] = curr_path.replace(val_str, placeholder)
                    if "url" in consumer:
                        consumer["url"] = consumer["url"].replace(val_str, placeholder)
                    dependencies.append(
                        {
                            "producer_step": i,
                            "consumer_step": j,
                            "variable": var_name,
                            "jsonpath": jsonpath,
                            "matched_value": val_str,
                            "location": "url_path",
                        }
                    )
                    consumer_matched = True

                # 2. Match in Query Params
                query_params = consumer.get("query_params") or {}
                for qk, qv in list(query_params.items()):
                    if str(qv) == val_str or (isinstance(qv, str) and val_str in qv):
                        if var_name is None:
                            var_name = _generate_variable_name(field_name, i, known_variables)
                        placeholder = f"{{{{{var_name}}}}}"
                        query_params[qk] = str(qv).replace(val_str, placeholder)
                        dependencies.append(
                            {
                                "producer_step": i,
                                "consumer_step": j,
                                "variable": var_name,
                                "jsonpath": jsonpath,
                                "matched_value": val_str,
                                "location": f"query_param({qk})",
                            }
                        )
                        consumer_matched = True

                # 3. Match in Headers
                headers = consumer.get("headers") or {}
                for hk, hv in list(headers.items()):
                    if val_str in str(hv):
                        if var_name is None:
                            var_name = _generate_variable_name(field_name, i, known_variables)
                        placeholder = f"{{{{{var_name}}}}}"
                        headers[hk] = str(hv).replace(val_str, placeholder)
                        dependencies.append(
                            {
                                "producer_step": i,
                                "consumer_step": j,
                                "variable": var_name,
                                "jsonpath": jsonpath,
                                "matched_value": val_str,
                                "location": f"header({hk})",
                            }
                        )
                        consumer_matched = True

                # 4. Match in Request Body
                req_body = consumer.get("request_body")
                if req_body:
                    if var_name is None:
                        var_name = _generate_variable_name(field_name, i, known_variables)
                    placeholder = f"{{{{{var_name}}}}}"
                    new_body, body_replaced = _replace_in_object(req_body, val_str, placeholder)
                    if body_replaced:
                        consumer["request_body"] = new_body
                        dependencies.append(
                            {
                                "producer_step": i,
                                "consumer_step": j,
                                "variable": var_name,
                                "jsonpath": jsonpath,
                                "matched_value": val_str,
                                "location": "request_body",
                            }
                        )
                        consumer_matched = True

                if consumer_matched and not extracted_for_step:
                    assert var_name is not None
                    extractions.append(
                        {
                            "variable": var_name,
                            "type": "jsonpath",
                            "expression": jsonpath,
                            "description": f"从步骤 {i + 1} 响应中提取 {field_name} (值: {val_str})",
                        }
                    )
                    extracted_for_step = True

    return {
        "parameterized_entries": parameterized,
        "discovered_dependencies": dependencies,
        "total_dependencies_count": len(dependencies),
    }
