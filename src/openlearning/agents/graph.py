"""Main graph compilation — assembles all agents into a LangGraph StateGraph.

This is the entry point for the multi-agent system.
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from openlearning.agents.analyzer import analyzer_agent
from openlearning.agents.builder import builder_agent
from openlearning.agents.collector import collector_agent
from openlearning.agents.evaluator import evaluator_engine
from openlearning.agents.memory import memory_agent
from openlearning.agents.planner import planner_agent
from openlearning.agents.reflector import reflector_agent
from openlearning.agents.state import AgentState
from openlearning.agents.supervisor import supervisor_decide


def build_graph() -> StateGraph:
    """Build the main agent graph with all sub-agents.

    Flow:
        START → memory → planner → collector → analyzer → evaluator
                          ↑                                    │
                          │         ┌──────────────────────────┘
                          │         ▼
                          │    (pass?)──yes──→ builder → END
                          │         │
                          │        no
                          │         │
                          │         ▼
                          └── reflector (strategy adjustment)
    """
    graph = StateGraph(AgentState)

    # Add all agent nodes
    graph.add_node("memory", memory_agent)
    graph.add_node("planner", planner_agent)
    graph.add_node("collector", collector_agent)
    graph.add_node("analyzer", analyzer_agent)
    graph.add_node("evaluator", evaluator_engine)
    graph.add_node("reflector", reflector_agent)
    graph.add_node("builder", builder_agent)

    # Define the flow
    graph.set_entry_point("memory")

    # Linear flow: memory → planner → collector → analyzer → evaluator
    graph.add_edge("memory", "planner")
    graph.add_edge("planner", "collector")
    graph.add_edge("collector", "analyzer")
    graph.add_edge("analyzer", "evaluator")

    # Conditional routing after evaluator
    graph.add_conditional_edges(
        "evaluator",
        _evaluator_routing,
        {
            "builder": "builder",
            "reflector": "reflector",
        },
    )

    # After reflector: go back to collector or to builder
    graph.add_conditional_edges(
        "reflector",
        _reflector_routing,
        {
            "collector": "collector",
            "builder": "builder",
        },
    )

    # Builder → END
    graph.add_edge("builder", END)

    return graph


def _evaluator_routing(state: AgentState) -> Literal["builder", "reflector"]:
    """Route after evaluation: build if passed, reflect if not."""
    evaluation = state.get("evaluation", {})

    if evaluation.get("pass", False):
        return "builder"

    # Check max iterations
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if iteration >= max_iterations:
        return "builder"

    return "reflector"


def _reflector_routing(state: AgentState) -> Literal["collector", "builder"]:
    """Route after reflection: retry collection or build."""
    reflection = state.get("reflection", {})

    if reflection.get("should_continue", False):
        return "collector"

    return "builder"


def compile_graph():
    """Compile the graph into a runnable."""
    graph = build_graph()
    return graph.compile()


# ── Convenience runner ───────────────────────────────────────

async def run_pipeline(
    user_request: str,
    user_profile: dict | None = None,
    max_iterations: int = 3,
) -> dict[str, Any]:
    """Run the full pipeline for a user request.

    Returns the final state with all agent outputs.
    """
    compiled = compile_graph()

    initial_state: AgentState = {
        "user_request": user_request,
        "user_profile": user_profile or {"level": "beginner", "lang": ["zh", "en"]},
        "iteration": 0,
        "max_iterations": max_iterations,
        "status": "running",
        "current_agent": "",
    }

    # Run the graph
    final_state = await compiled.ainvoke(initial_state)

    return final_state
