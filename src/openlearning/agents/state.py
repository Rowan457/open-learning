"""Shared state definition for the multi-agent system.

All agents read from and write to this TypedDict via LangGraph StateGraph.
"""

import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    """Global shared state for all agents."""

    # ── User Input ───────────────────────────────────────────
    user_request: str  # "我想学 Rust"
    user_profile: dict  # {"level": "intermediate", "lang": ["zh","en"]}

    # ── Memory Output ────────────────────────────────────────
    user_memory: dict  # three-layer memory: project/preference/learning
    avoid_list: Annotated[list[str], operator.add]  # already-recommended URLs

    # ── Planner Output ───────────────────────────────────────
    knowledge_graph: dict  # nodes + edges + dependencies
    search_queries: Annotated[list[str], operator.add]  # generated search keywords
    learning_plan: dict  # full plan with tree + crawl tasks

    # ── Collector Output ─────────────────────────────────────
    raw_resources: Annotated[list[dict], operator.add]  # collected raw resources
    collected_count: int  # total collected so far
    sources_queried: Annotated[list[str], operator.add]  # which sources were queried

    # ── Analyzer Output ──────────────────────────────────────
    analyzed_resources: Annotated[list[dict], operator.add]  # scored + summarized
    avg_quality_score: float
    extracted_concepts: Annotated[list[dict], operator.add]  # knowledge concepts
    concept_relations: Annotated[list[dict], operator.add]  # prerequisite/extends/related

    # ── Evaluation Engine Output ─────────────────────────────
    evaluation: dict  # rule engine results
    iteration: int  # current iteration count

    # ── Reflector Output ─────────────────────────────────────
    reflection: dict  # LLM strategy adjustment suggestions

    # ── Builder Output ───────────────────────────────────────
    learning_system: dict  # generated site path + graph + path

    # ── Supervisor ───────────────────────────────────────────
    supervisor_log: Annotated[list[dict], operator.add]  # decision history
    _next_agent: str  # supervisor's routing decision (internal)

    # ── Flow Control ─────────────────────────────────────────
    current_agent: str  # name of the agent currently executing
    status: str  # running / done / error
    max_iterations: int  # max collection iterations (default 3)
    search_errors: Annotated[list[str], operator.add]  # search error log
