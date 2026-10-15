"""Workflow Bi-Directional Context Variable Dataflow Topology Validator (T3.2).

Performs static analysis on workflow DAG nodes to detect:
1. Undeclared / phantom variables referenced via {{var}} before production.
2. Reverse-order dataflow references (consuming variables produced by downstream nodes).
3. Variable lineage mapping (producers -> consumers).
4. Unused produced variables warnings.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.workflow_dag_engine import (
    validate_and_toposort_workflow,
)

logger = logging.getLogger(__name__)

VAR_EXTRACTION_REGEX = re.compile(r"\{\{(\w+)\}\}")


class WorkflowDataflowError(ValueError):
    """Raised when dataflow validation detects illegal variable dependencies."""


def extract_consumed_variables(data: Any) -> set[str]:
    """Recursively search for all {{variable_name}} tokens in configuration values."""
    found: set[str] = set()
    if isinstance(data, str):
        found.update(VAR_EXTRACTION_REGEX.findall(data))
    elif isinstance(data, dict):
        for v in data.values():
            found.update(extract_consumed_variables(v))
    elif isinstance(data, list):
        for item in data:
            found.update(extract_consumed_variables(item))
    return found


def extract_produced_variables(config: dict[str, Any]) -> set[str]:
    """Extract variable names produced by a node through extractions."""
    extractions = config.get("extractions") or {}
    if isinstance(extractions, dict):
        return {str(k).strip() for k in extractions.keys() if str(k).strip()}
    return set()


def build_ancestor_map(nodes: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Compute transitive ancestor sets for each node in a topologically sorted DAG."""
    parent_map: dict[str, list[str]] = {}
    for node in nodes:
        nid = str(node.get("id"))
        deps = node.get("depends_on") or []
        if isinstance(deps, str):
            deps = [deps]
        parent_map[nid] = [str(d).strip() for d in deps if str(d).strip()]

    ancestors: dict[str, set[str]] = {}
    for node in nodes:
        nid = str(node.get("id"))
        visited: set[str] = set()
        queue = list(parent_map.get(nid, []))
        while queue:
            curr = queue.pop()
            if curr not in visited:
                visited.add(curr)
                queue.extend(parent_map.get(curr, []))
        ancestors[nid] = visited

    return ancestors


def validate_workflow_dataflow_topology(
    nodes: list[dict[str, Any]],
    initial_context: dict[str, Any] | set[str] | list[str] | None = None,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Validate dataflow consistency across all workflow nodes."""
    # 1. Topological sort and graph cycle validation
    sorted_nodes = validate_and_toposort_workflow(nodes)
    ancestors = build_ancestor_map(sorted_nodes)

    # Initial available variables (from initial context or built-ins like trace_id)
    initial_vars: set[str] = {"trace_id", "timestamp", "NOW"}
    if isinstance(initial_context, dict):
        initial_vars.update(initial_context.keys())
    elif isinstance(initial_context, (set, list)):
        initial_vars.update(str(v) for v in initial_context)

    # 2. Map produced variables by node
    node_produces: dict[str, set[str]] = {}
    producer_of_var: dict[str, str] = {}  # var_name -> node_id
    for node in sorted_nodes:
        nid = str(node.get("id"))
        cfg = node.get("config") or {}
        produced = extract_produced_variables(cfg)
        node_produces[nid] = produced
        for var in produced:
            producer_of_var[var] = nid

    # 3. Analyze consumed variables and check reachability
    missing_variables: list[dict[str, Any]] = []
    reverse_references: list[dict[str, Any]] = []
    variable_lineage: dict[str, dict[str, Any]] = {}
    all_consumed: set[str] = set()

    for node in sorted_nodes:
        nid = str(node.get("id"))
        nname = str(node.get("name") or nid)
        cfg = node.get("config") or {}
        consumed = extract_consumed_variables(cfg)
        all_consumed.update(consumed)

        # Available variables at this node: initial_vars + union(produces(P) for P in ancestors[nid])
        available_at_node: set[str] = set(initial_vars)
        for ancestor_id in ancestors.get(nid, set()):
            available_at_node.update(node_produces.get(ancestor_id, set()))

        for var in consumed:
            # Record lineage
            if var not in variable_lineage:
                variable_lineage[var] = {
                    "variable": var,
                    "producer_node": producer_of_var.get(var, "initial_context" if var in initial_vars else None),
                    "consumers": [],
                }
            variable_lineage[var]["consumers"].append(nid)

            # Check if variable is available
            if var not in available_at_node:
                # Check if it is produced downstream / reverse-order
                if var in producer_of_var:
                    producer_id = producer_of_var[var]
                    reverse_references.append(
                        {
                            "consumer_node": nid,
                            "consumer_name": nname,
                            "producer_node": producer_id,
                            "variable": var,
                            "error": f"节点 '{nname}' (id:{nid}) 引用了后续或非父节点 (id:{producer_id}) 产出的变量: '{{{{{var}}}}}'",
                        }
                    )
                else:
                    missing_variables.append(
                        {
                            "consumer_node": nid,
                            "consumer_name": nname,
                            "variable": var,
                            "error": f"节点 '{nname}' (id:{nid}) 引用了未声明的未知变量: '{{{{{var}}}}}'",
                        }
                    )

    # 4. Check for unused variables (warning)
    unused_variables: list[dict[str, Any]] = []
    for var, prod_nid in producer_of_var.items():
        if var not in all_consumed:
            unused_variables.append(
                {
                    "producer_node": prod_nid,
                    "variable": var,
                    "note": f"节点 (id:{prod_nid}) 提取的变量 '{var}' 未被任何后续节点消费",
                }
            )

    is_valid = len(missing_variables) == 0 and len(reverse_references) == 0

    if strict and not is_valid:
        error_details = []
        if reverse_references:
            error_details.append(reverse_references[0]["error"])
        if missing_variables:
            error_details.append(missing_variables[0]["error"])
        raise WorkflowDataflowError("; ".join(error_details))

    return {
        "valid": is_valid,
        "total_nodes": len(sorted_nodes),
        "total_variables": len(variable_lineage),
        "missing_variable_count": len(missing_variables),
        "reverse_reference_count": len(reverse_references),
        "unused_variable_count": len(unused_variables),
        "missing_variables": missing_variables,
        "reverse_references": reverse_references,
        "unused_variables": unused_variables,
        "variable_lineage": list(variable_lineage.values()),
    }
