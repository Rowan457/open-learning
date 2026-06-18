"""Supervisor Agent — LLM-driven orchestration.

The Supervisor observes global state and reasons about which agent to call next.
This is a simplified rule-based version; the LLM-driven version uses create_react_agent.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


# ── Supervisor Decision Logic ────────────────────────────────

def supervisor_decide(state: AgentState) -> str:
    """Decide the next agent to call based on current state.

    This is the rule-based fallback. The LLM-driven supervisor
    replaces this with create_react_agent.
    """
    current = state.get("current_agent", "")
    status = state.get("status", "")

    # If done, stop
    if status == "done":
        return "end"

    # If error, stop
    if status == "error":
        return "end"

    # First call: start with memory
    if not current:
        return "memory"

    # Routing logic
    routing = {
        "memory": "planner",
        "planner": "collector",
        "collector": "analyzer",
        "analyzer": "evaluator",
        "evaluator": _evaluator_route,
        "reflector": _reflector_route,
        "builder": "end",
    }

    handler = routing.get(current)
    if handler is None:
        return "end"

    if callable(handler):
        return handler(state)

    return handler


def _evaluator_route(state: AgentState) -> str:
    """Route after evaluation."""
    evaluation = state.get("evaluation", {})

    if evaluation.get("pass", False):
        return "builder"

    # Check if we should reflect or retry
    iteration = state.get("iteration", 0)
    if iteration >= 3:
        # Max iterations reached, build anyway
        return "builder"

    # Need more resources — go to reflector for strategy adjustment
    return "reflector"


def _reflector_route(state: AgentState) -> str:
    """Route after reflection."""
    reflection = state.get("reflection", {})

    if reflection.get("should_continue", False):
        # Go back to collector for another round
        return "collector"

    # No more adjustments needed, build
    return "builder"


# ── Supervisor Node (for LangGraph) ─────────────────────────

async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Supervisor node in the LangGraph state graph.

    This node doesn't modify state — it's used for routing.
    The actual routing is done by the conditional edges.
    """
    return {
        "current_agent": "supervisor",
    }
