"""Memory Agent — user memory management subgraph.

Queries three-layer memory: project, preference, learning.
Uses memory/ module functions instead of inline duplicates.
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
    knowledge_graph = state.get("knowledge_graph", {})

    print(f"[Memory] 查询用户记忆: {user_id}")

    # ── Layer 1: Project Memory ──────────────────────────────
    history = await _query_project_history(user_id)
    avoid_list = await _query_avoid_list(user_id)
    similar_project = _find_similar_project(history, user_request)

    # ── Layer 2: Preference Memory ───────────────────────────
    preferences = await _learn_preferences(user_id)

    # ── Layer 3: Learning Memory ─────────────────────────────
    mastery = await _query_mastery(user_id)

    # Use the richer gaps analysis from memory/ module
    gaps = _analyze_gaps(knowledge_graph, mastery)

    # ── Generate Suggestions ─────────────────────────────────
    suggestions = _generate_suggestions(mastery, gaps, preferences)

    mastered_count = len(mastery.get("mastered", []))
    learning_count = len(mastery.get("learning", []))
    print(f"[Memory] 已掌握: {mastered_count}, 学习中: {learning_count}, 缺口: {len(gaps)}")

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

        prefs = await get_preferences.ainvoke({"user_id": user_id})

        # Enrich with memory/preferences.py if interaction data available
        try:
            from openlearning.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT r.resource_type, r.language, ri.event "
                    "FROM resource_interactions ri "
                    "JOIN resources r ON ri.resource_id = r.id "
                    "WHERE ri.user_id = :uid ORDER BY ri.created_at DESC LIMIT 50"
                ), {"uid": user_id})
                interactions = [dict(zip(result.keys(), row)) for row in result.fetchall()]

            if interactions:
                from openlearning.memory.preferences import infer_preferences
                inferred = infer_preferences(interactions)
                # Merge: inferred overrides hardcoded defaults
                for key in ("difficulty", "learning_style"):
                    if inferred.get(key) and inferred[key] != prefs.get(key):
                        prefs[key] = inferred[key]
        except Exception:
            pass

        return prefs
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


def _analyze_gaps(graph: dict, mastery: dict) -> list[dict]:
    """Compare knowledge graph vs mastery to find gaps.

    Uses memory/gaps.py for enriched gap analysis (sorted by importance).
    """
    try:
        from openlearning.memory.gaps import analyze_knowledge_gaps

        mastery_list = (
            mastery.get("mastered", [])
            + mastery.get("learning", [])
            + mastery.get("not_started", [])
        )
        return analyze_knowledge_gaps(graph, mastery_list)
    except Exception:
        # Fallback to simple version
        if not graph:
            return []
        nodes = graph.get("nodes", [])
        mastered_ids = {m.get("concept_id", "") for m in mastery.get("mastered", [])}
        learning_ids = {m.get("concept_id", "") for m in mastery.get("learning", [])}
        covered = mastered_ids | learning_ids
        return [{"concept_id": n.get("id"), "name": n.get("name"), "importance": n.get("importance", 0.5)}
                for n in nodes if n.get("id") not in covered]


def _generate_suggestions(mastery: dict, gaps: list, preferences: dict) -> list[str]:
    """Generate personalized learning suggestions."""
    suggestions = []

    if mastery.get("due_reviews"):
        suggestions.append("有概念需要复习，建议先巩固已有知识")

    if gaps:
        # gaps can be list[str] (simple) or list[dict] (enriched)
        if isinstance(gaps[0], dict):
            top_gaps = [g.get("name", g.get("concept_id", "")) for g in gaps[:3]]
        else:
            top_gaps = gaps[:3]
        suggestions.append(f"发现 {len(gaps)} 个知识缺口，优先补充: {', '.join(top_gaps)}")

    if not mastery.get("mastered") and not mastery.get("learning"):
        suggestions.append("这是全新领域，建议从基础概念开始")

    prefs_diff = preferences.get("difficulty", "")
    if prefs_diff:
        suggestions.append(f"推荐难度: {prefs_diff}")

    return suggestions
