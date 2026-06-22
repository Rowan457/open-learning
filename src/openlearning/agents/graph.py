"""Main graph compilation — assembles all agents into a LangGraph StateGraph.

Supervisor-driven dynamic orchestration: every agent returns to the Supervisor,
which decides the next step based on current state.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from openlearning.agents.analyzer import analyzer_agent
from openlearning.agents.builder import builder_agent
from openlearning.agents.collector import collector_agent
from openlearning.agents.evaluator import evaluator_engine
from openlearning.agents.memory import memory_agent
from openlearning.agents.planner import planner_agent
from openlearning.agents.reflector import reflector_agent
from openlearning.agents.state import AgentState
from openlearning.agents.supervisor import supervisor_node, supervisor_route


def build_graph() -> StateGraph:
    """Build the main agent graph with Supervisor-driven routing.

    Flow:
        START → supervisor → [agent] → supervisor → ... → END

    The Supervisor observes state after each agent and decides the next step.
    """
    graph = StateGraph(AgentState)

    # Add all agent nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("memory", memory_agent)
    graph.add_node("planner", planner_agent)
    graph.add_node("collector", collector_agent)
    graph.add_node("analyzer", analyzer_agent)
    graph.add_node("evaluator", evaluator_engine)
    graph.add_node("reflector", reflector_agent)
    graph.add_node("builder", builder_agent)

    # Entry: go to supervisor first
    graph.set_entry_point("supervisor")

    # Supervisor routes to any agent
    graph.add_conditional_edges(
        "supervisor",
        supervisor_route,
        {
            "memory": "memory",
            "planner": "planner",
            "collector": "collector",
            "analyzer": "analyzer",
            "evaluator": "evaluator",
            "reflector": "reflector",
            "builder": "builder",
            "end": END,
        },
    )

    # Every agent returns to supervisor
    for agent_name in ["memory", "planner", "collector", "analyzer", "evaluator", "reflector", "builder"]:
        graph.add_edge(agent_name, "supervisor")

    return graph


def compile_graph():
    """Compile the graph into a runnable."""
    graph = build_graph()
    compiled = graph.compile()

    # Debug: print state at each step
    original_invoke = compiled.ainvoke

    async def debug_invoke(input_data, **kwargs):
        result = await original_invoke(input_data, **kwargs)
        # Print final state summary
        print(f"\n[Graph] 最终状态:")
        print(f"  raw_resources: {len(result.get('raw_resources', []))}")
        print(f"  analyzed_resources: {len(result.get('analyzed_resources', []))}")
        print(f"  evaluation: {result.get('evaluation', {})}")

        # Print supervisor decisions
        log = result.get("supervisor_log", [])
        if log:
            print(f"  supervisor 决策 ({len(log)} 次):")
            for entry in log:
                print(f"    {entry.get('from', '?')} → {entry.get('to', '?')}: {entry.get('reason', '')}")

        return result

    compiled.ainvoke = debug_invoke
    return compiled


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
