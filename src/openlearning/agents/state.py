"""Shared state definition for the multi-agent system.

All agents read from and write to this TypedDict via LangGraph StateGraph.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Global shared state for all agents."""

    # ── User Input ───────────────────────────────────────────
    user_request: str  # "我想学 Rust"
    user_profile: dict  # {"level": "intermediate", "lang": ["zh","en"]}

    # ── Memory Output ────────────────────────────────────────
    user_memory: dict  # three-layer memory: project/preference/learning
    avoid_list: list[str]  # already-recommended URLs (for dedup)

    # ── Planner Output ───────────────────────────────────────
    knowledge_graph: dict  # nodes + edges + dependencies
    search_queries: list[str]  # generated search keywords
    learning_plan: dict  # full plan with tree + crawl tasks

    # ── Collector Output ─────────────────────────────────────
    raw_resources: list[dict]  # collected raw resources
    collected_count: int  # total collected so far
    sources_queried: list[str]  # which sources were queried

    # ── Analyzer Output ──────────────────────────────────────
    analyzed_resources: list[dict]  # scored + summarized resources
    avg_quality_score: float
    extracted_concepts: list[dict]  # knowledge concepts
    concept_relations: list[dict]  # prerequisite/extends/related edges

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
