"""Workflow Canvas Step-by-Step Breakpoint Debugger and Dataflow Watcher (T3.3).

Provides:
1. Breakpoint setting and management on workflow DAG nodes.
2. Step-by-step single node execution (Step Over) and breakpoint resumption (Resume).
3. Live dataflow variable watchers with change tracking (context_diff).
4. Frozen execution snapshot inspection for interactive debugging.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

from app.services.workflow_dag_engine import (
    execute_single_node,
    validate_and_toposort_workflow,
)

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_DEBUG_SESSIONS: dict[str, WorkflowDebugSession] = {}


class WorkflowDebuggerError(ValueError):
    """Raised when debug session operation is invalid or session not found."""


class WorkflowDebugSession:
    """State machine representing an active breakpoint debugging session."""

    def __init__(
        self,
        session_id: str,
        workflow_graph: dict[str, Any],
        breakpoints: list[str] | set[str] | None = None,
        initial_context: dict[str, Any] | None = None,
        watchers: list[str] | None = None,
    ):
        self.session_id = session_id
        self.workflow_graph = workflow_graph
        raw_nodes = workflow_graph.get("nodes") or []
        self.sorted_nodes = validate_and_toposort_workflow(raw_nodes)

        raw_bps = breakpoints or []
        self.breakpoints: set[str] = {str(b).strip() for b in raw_bps if str(b).strip()}
        self.watchers: list[str] = [str(w).strip() for w in (watchers or []) if str(w).strip()]

        self.current_index: int = 0
        self.context: dict[str, Any] = dict(initial_context or {})
        self.previous_context: dict[str, Any] = dict(self.context)
        self.history: list[dict[str, Any]] = []
        self.state: str = "paused"  # paused | completed | error
        self.error: str | None = None
        self.created_at: float = time.time()
        self.updated_at: float = self.created_at

    def _evaluate_watchers(self) -> list[dict[str, Any]]:
        results = []
        for w in self.watchers:
            val = self.context.get(w)
            old_val = self.previous_context.get(w)
            results.append(
                {
                    "name": w,
                    "value": val,
                    "type": type(val).__name__ if val is not None else "NoneType",
                    "changed_in_last_step": val != old_val,
                }
            )
        return results

    def _compute_context_diff(self) -> dict[str, dict[str, Any]]:
        diff: dict[str, dict[str, Any]] = {}
        all_keys = set(self.context.keys()) | set(self.previous_context.keys())
        for k in all_keys:
            old = self.previous_context.get(k)
            new = self.context.get(k)
            if old != new:
                diff[k] = {"old": old, "new": new}
        return diff

    def snapshot(self) -> dict[str, Any]:
        """Return an immutable inspection snapshot of the current debug state."""
        current_node = self.sorted_nodes[self.current_index] if self.current_index < len(self.sorted_nodes) else None
        next_node = (
            self.sorted_nodes[self.current_index + 1] if self.current_index + 1 < len(self.sorted_nodes) else None
        )

        return {
            "session_id": self.session_id,
            "state": self.state,
            "current_node_index": self.current_index,
            "total_nodes": len(self.sorted_nodes),
            "current_node": current_node,
            "next_node": next_node,
            "breakpoints": sorted(self.breakpoints),
            "context": dict(self.context),
            "context_diff": self._compute_context_diff(),
            "watchers": self._evaluate_watchers(),
            "history": list(self.history),
            "error": self.error,
        }

    async def step_over(self) -> dict[str, Any]:
        """Execute the node at the current pointer and advance to the next node."""
        if self.current_index >= len(self.sorted_nodes):
            self.state = "completed"
            return self.snapshot()

        node = self.sorted_nodes[self.current_index]
        nid = str(node.get("id"))
        ntype = str(node.get("type") or "http")
        nname = str(node.get("name") or nid)
        config = node.get("config") or {}

        self.previous_context = dict(self.context)
        node_start = time.monotonic()
        node_res: dict[str, Any] = {"id": nid, "name": nname, "type": ntype}

        try:
            output = await execute_single_node(node, self.context)
            node_res["status"] = "passed" if output.get("success", True) else "failed"
            node_res["output"] = output

            # Apply extractions
            extractions = config.get("extractions") or {}
            if isinstance(extractions, dict):
                for var_name in extractions:
                    self.context[var_name] = output.get("body") or output.get("value")

            if node_res["status"] == "failed":
                self.state = "error"
                self.error = f"节点 {nname} 执行失败: {output}"

        except Exception as exc:
            logger.warning("Debug execution failed on node %s: %s", nid, exc)
            node_res["status"] = "failed"
            node_res["error"] = str(exc)
            self.state = "error"
            self.error = str(exc)

        node_res["duration_ms"] = round((time.monotonic() - node_start) * 1000.0, 2)
        self.history.append(node_res)
        self.current_index += 1
        self.updated_at = time.time()

        if self.state != "error":
            if self.current_index >= len(self.sorted_nodes):
                self.state = "completed"
            else:
                self.state = "paused"

        return self.snapshot()

    async def resume(self) -> dict[str, Any]:
        """Continue execution until the next breakpoint or completion."""
        # Execute current node if paused
        if self.state in ("completed", "error"):
            return self.snapshot()

        # Step over at least once to move off the current breakpoint
        await self.step_over()

        # Keep running until we hit another breakpoint, complete, or error
        while self.state == "paused" and self.current_index < len(self.sorted_nodes):
            curr_node = self.sorted_nodes[self.current_index]
            curr_id = str(curr_node.get("id"))
            if curr_id in self.breakpoints:
                # Pause at breakpoint
                self.state = "paused"
                break
            await self.step_over()

        return self.snapshot()


def create_debug_session(
    workflow_graph: dict[str, Any],
    breakpoints: list[str] | None = None,
    initial_context: dict[str, Any] | None = None,
    watchers: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new debug session and pause at the entry point."""
    sid = f"dbg_{uuid.uuid4().hex[:12]}"
    session = WorkflowDebugSession(
        session_id=sid,
        workflow_graph=workflow_graph,
        breakpoints=breakpoints,
        initial_context=initial_context,
        watchers=watchers,
    )
    with _LOCK:
        _DEBUG_SESSIONS[sid] = session
    return session.snapshot()


def get_debug_session(session_id: str) -> dict[str, Any]:
    """Inspect active debug session state."""
    with _LOCK:
        session = _DEBUG_SESSIONS.get(session_id)
    if not session:
        raise WorkflowDebuggerError(f"未找到调试会话: {session_id}")
    return session.snapshot()


async def step_debug_session(session_id: str) -> dict[str, Any]:
    """Step over the current node in the debug session."""
    with _LOCK:
        session = _DEBUG_SESSIONS.get(session_id)
    if not session:
        raise WorkflowDebuggerError(f"未找到调试会话: {session_id}")
    return await session.step_over()


async def resume_debug_session(session_id: str) -> dict[str, Any]:
    """Resume execution until next breakpoint or completion."""
    with _LOCK:
        session = _DEBUG_SESSIONS.get(session_id)
    if not session:
        raise WorkflowDebuggerError(f"未找到调试会话: {session_id}")
    return await session.resume()


def stop_debug_session(session_id: str) -> bool:
    """Terminate and delete a debug session."""
    with _LOCK:
        return _DEBUG_SESSIONS.pop(session_id, None) is not None
