"""Tool Router — selects the best tools for a given task.

Uses LLM reasoning (or rule-based fallback) to plan tool usage.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


async def tool_router_agent(state: AgentState) -> dict[str, Any]:
    """Tool Router: select best tools based on task context.

    Reads: current_task, task_context
    Writes: tool_plan
    """
    task = state.get("current_agent", "")
    context = state.get("learning_plan", {})

    # Rule-based tool selection
    tool_plan = _select_tools(task, context)

    return {
        "tool_plan": tool_plan,
        "current_agent": "tool_router",
    }


def _select_tools(task: str, context: dict) -> dict:
    """Select tools based on task type."""
    analysis = context.get("analysis", {})
    topic = analysis.get("topic", "")
    languages = analysis.get("languages", ["en"])

    # Default tool plan
    plan = {
        "tools": [],
        "params": [],
        "reason": "",
    }

    if task in ("collector", "collect"):
        # Determine which search tools to use
        tools = ["web_search"]
        params = [{"query": f"{topic} tutorial", "max_results": 15}]

        if "paper" in str(context).lower() or "arxiv" in str(context).lower():
            tools.append("arxiv_search")
            params.append({"query": topic, "max_results": 10})

        if "video" in str(context).lower():
            tools.append("youtube_search")
            params.append({"query": f"{topic} tutorial", "max_results": 10})

        if "code" in str(context).lower() or "github" in str(context).lower():
            tools.append("github_search")
            params.append({"query": topic})

        plan = {
            "tools": tools,
            "params": params,
            "reason": f"Collecting resources for '{topic}' across multiple sources",
        }

    elif task in ("analyzer", "analyze"):
        plan = {
            "tools": ["fetch_page", "score", "summarize", "tag", "extract_knowledge"],
            "params": [],
            "reason": "Analyzing collected resources: fetch content, score, summarize, extract knowledge",
        }

    elif task in ("builder", "build"):
        plan = {
            "tools": ["build_learning_system", "save_resource"],
            "params": [],
            "reason": "Building learning system site from knowledge graph",
        }

    return plan
