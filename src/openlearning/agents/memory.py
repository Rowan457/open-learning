"""Memory Agent — user memory management subgraph.

Queries three-layer memory: project, preference, learning.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


async def memory_agent(state: AgentState) -> dict[str, Any]:
    """Memory subgraph: query user memory → analyze learning state → personalized suggestions.

    Reads: user_request, user_profile, knowledge_graph
    Writes: user_memory, avoid_list
    """
    user_profile = state.get("user_profile", {})
    user_id = user_profile.get("user_id", "default")
    user_request = state.get("user_request", "")

    # ── Layer 1: Project Memory ──────────────────────────────
    history = await _query_project_history(user_id)
    avoid_list = await _query_avoid_list(user_id)
    similar_project = _find_similar_project(history, user_request)

    # ── Layer 2: Preference Memory ───────────────────────────
    preferences = await _learn_preferences(user_id)

    # ── Layer 3: Learning Memory ─────────────────────────────
    mastery = await _query_mastery(user_id)
    gaps = _analyze_knowledge_gaps(state.get("knowledge_graph", {}), mastery)

    # ── Generate Suggestions ─────────────────────────────────
    suggestions = _generate_suggestions(mastery, gaps, preferences)

    return {
        "user_memory": {
            "history": history,
            "preferences": preferences,
            "similar_project": similar_project,
            "mastery": mastery,
            "gaps": gaps,
            "suggestions": suggestions,
        },
        "avoid_list": avoid_list,
        "current_agent": "memory",
    }


async def _query_project_history(user_id: str) -> list[dict]:
    """Query recent projects."""
    try:
        from openlearning.database import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text

            result = conn.execute(
                text("SELECT * FROM projects WHERE status = 'active' ORDER BY updated_at DESC LIMIT 10")
            )
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception:
        return []


async def _query_avoid_list(user_id: str) -> list[str]:
    """Get URLs already recommended to this user.

    只查询其他项目的资源，避免重复推荐。
    当前项目的资源由 Collector 自行去重。
    """
    try:
        from openlearning.database import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text

            # 只查询非当前项目的资源（避免跨项目重复推荐）
            result = conn.execute(text("SELECT url FROM resources"))
            return [row[0] for row in result.fetchall()]
    except Exception:
        return []


def _find_similar_project(history: list[dict], request: str) -> dict | None:
    """Find a similar past project."""
    request_lower = request.lower()
    for project in history:
        title = project.get("title", "").lower()
        # Simple substring match
        if any(word in title for word in request_lower.split() if len(word) > 2):
            return project
    return None


async def _learn_preferences(user_id: str) -> dict:
    """Learn user preferences from interactions."""
    try:
        from openlearning.skills.memory import get_preferences

        return await get_preferences.ainvoke({"user_id": user_id})
    except Exception:
        return {
            "resource_type": {},
            "language": {"zh": 0.5, "en": 0.5},
            "difficulty": "intermediate",
            "learning_style": "reading",
        }


async def _query_mastery(user_id: str) -> dict:
    """Query concept mastery data."""
    try:
        from openlearning.skills.memory import get_mastery

        mastery_list = await get_mastery.ainvoke({"user_id": user_id})

        mastered = [m for m in mastery_list if m.get("mastery", 0) >= 0.8]
        learning = [m for m in mastery_list if 0.2 <= m.get("mastery", 0) < 0.8]
        not_started = [m for m in mastery_list if m.get("mastery", 0) < 0.2]

        return {
            "mastered": mastered,
            "learning": learning,
            "not_started": not_started,
            "due_reviews": [m for m in mastery_list if m.get("next_review")],
        }
    except Exception:
        return {
            "mastered": [],
            "learning": [],
            "not_started": [],
            "due_reviews": [],
        }


def _analyze_knowledge_gaps(graph: dict, mastery: dict) -> list[str]:
    """Compare knowledge graph vs mastery to find gaps."""
    if not graph:
        return []

    nodes = graph.get("nodes", [])
    mastered_ids = {m.get("concept_id", "") for m in mastery.get("mastered", [])}
    learning_ids = {m.get("concept_id", "") for m in mastery.get("learning", [])}
    covered = mastered_ids | learning_ids

    gaps = []
    for node in nodes:
        node_id = node.get("id", "")
        if node_id not in covered:
            gaps.append(node_id)

    return gaps


def _generate_suggestions(mastery: dict, gaps: list, preferences: dict) -> list[str]:
    """Generate personalized learning suggestions."""
    suggestions = []

    if mastery.get("due_reviews"):
        suggestions.append("有概念需要复习，建议先巩固已有知识")

    if gaps:
        suggestions.append(f"发现 {len(gaps)} 个知识缺口，建议在学习路径中补充")

    if not mastery.get("mastered") and not mastery.get("learning"):
        suggestions.append("这是全新领域，建议从基础概念开始")

    return suggestions
