"""Shared state definition for the multi-agent system.

All agents read from and write to this TypedDict via LangGraph StateGraph.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def _merge_list(existing: list, new: list) -> list:
    """Merge strategy for list fields: replace with new value."""
    return new


class AgentState(TypedDict, total=False):
    """Global shared state for all agents."""

    # ── User Input ───────────────────────────────────────────
    user_request: str  # "我想学 Rust"
    user_profile: dict  # {"level": "intermediate", "lang": ["zh","en"]}

    # ── Memory Output ────────────────────────────────────────
    user_memory: dict  # three-layer memory: project/preference/learning
    avoid_list: Annotated[list[str], _merge_list]  # already-recommended URLs

    # ── Planner Output ───────────────────────────────────────
    knowledge_graph: dict  # nodes + edges + dependencies
    search_queries: Annotated[list[str], _merge_list]  # generated search keywords
    learning_plan: dict  # full plan with tree + crawl tasks

    # ── Collector Output ─────────────────────────────────────
    raw_resources: Annotated[list[dict], _merge_list]  # collected raw resources
    collected_count: int  # total collected so far
    sources_queried: Annotated[list[str], _merge_list]  # which sources were queried

    # ── Analyzer Output ──────────────────────────────────────
    analyzed_resources: Annotated[list[dict], _merge_list]  # scored + summarized
    avg_quality_score: float
    extracted_concepts: Annotated[list[dict], _merge_list]  # knowledge concepts
    concept_relations: Annotated[list[dict], _merge_list]  # prerequisite/extends/related

    # ── Evaluation Engine Output ─────────────────────────────
    evaluation: dict  # rule engine results
    iteration: int  # current iteration count

    # ── Reflector Output ─────────────────────────────────────
    reflection: dict  # LLM strategy adjustment suggestions

    # ── Builder Output ───────────────────────────────────────
    learning_system: dict  # generated site path + graph + path

    # ── Flow Control ─────────────────────────────────────────
    current_agent: str  # name of the agent currently executing
    status: str  # running / done / error
    max_iterations: int  # max collection iterations (default 3)
    search_errors: Annotated[list[str], _merge_list]  # search error log
