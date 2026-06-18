"""Memory Skill — user memory operations.

Tools: get_mastery, update_mastery, get_preferences, record_event
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ── Input Schemas ────────────────────────────────────────────

class GetMasteryInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    domain: str | None = Field(default=None, description="知识领域过滤")


class UpdateMasteryInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    concept_id: str = Field(description="概念 ID")
    event: str = Field(description="学习事件: started/practiced/mastered/reviewed/tested")
    score: float | None = Field(default=None, description="测验得分 (如有)")
    time_spent: int | None = Field(default=None, description="学习时长(秒)")


class GetPreferencesInput(BaseModel):
    user_id: str = Field(description="用户 ID")


class RecordEventInput(BaseModel):
    user_id: str = Field(description="用户 ID")
    concept_id: str = Field(description="概念 ID")
    event: str = Field(description="事件类型")
    resource_id: str | None = Field(default=None, description="关联资源 ID")
    score: float | None = Field(default=None)
    time_spent: int | None = Field(default=None)


# ── Get Mastery ──────────────────────────────────────────────

@tool("get_mastery", args_schema=GetMasteryInput)
async def get_mastery(user_id: str, domain: str | None = None) -> list[dict[str, Any]]:
    """查询用户的概念掌握度列表。

    返回 [{concept_id, name, mastery, stability, review_count, next_review}]。
    """
    from openlearning.database import get_engine

    engine = get_engine()

    sql = """
        SELECT cm.concept_id, c.name, c.domain, c.type, c.difficulty,
               cm.mastery, cm.stability, cm.review_count,
               cm.last_practiced, cm.next_review, cm.learned_at
        FROM concept_mastery cm
        JOIN concepts c ON cm.concept_id = c.id
        WHERE cm.user_id = :user_id
    """
    params: dict[str, Any] = {"user_id": user_id}

    if domain:
        sql += " AND (c.domain = :domain OR c.domain IS NULL)"
        params["domain"] = domain

    sql += " ORDER BY cm.mastery DESC"

    with engine.connect() as conn:
        from sqlalchemy import text

        result = conn.execute(text(sql), params)
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


# ── Update Mastery ───────────────────────────────────────────

@tool("update_mastery", args_schema=UpdateMasteryInput)
async def update_mastery(
    user_id: str,
    concept_id: str,
    event: str,
    score: float | None = None,
    time_spent: int | None = None,
) -> dict[str, Any]:
    """更新概念掌握度。

    基于学习事件调整 mastery 值和间隔重复参数。
    返回 {success, new_mastery, next_review}。
    """
    from datetime import timedelta

    from openlearning.database import get_engine

    engine = get_engine()
    now = datetime.utcnow()

    # Single connection for read + write (transactional consistency)
    with engine.begin() as conn:
        from sqlalchemy import text

        result = conn.execute(
            text("SELECT * FROM concept_mastery WHERE user_id = :uid AND concept_id = :cid"),
            {"uid": user_id, "cid": concept_id},
        ).fetchone()

        if result:
            current_mastery = result.mastery
            stability = result.stability
            review_count = result.review_count
        else:
            current_mastery = 0.0
            stability = 1.0
            review_count = 0
            conn.execute(
                text("""
                    INSERT INTO concept_mastery (id, user_id, concept_id, mastery, stability, learned_at)
                    VALUES (:id, :uid, :cid, 0.0, 1.0, :now)
                """),
                {"id": f"{user_id}_{concept_id}", "uid": user_id, "cid": concept_id, "now": now},
            )

    # Calculate new mastery based on event
    mastery_delta = {
        "started": 0.1,
        "practiced": 0.15,
        "mastered": 0.4,
        "reviewed": 0.1,
        "tested": 0.0,  # depends on score
    }

    delta = mastery_delta.get(event, 0.1)

    # For tests, use score
    if event == "tested" and score is not None:
        delta = (score / 100.0) * 0.3  # up to 0.3 from a test

    new_mastery = min(1.0, current_mastery + delta)

    # SM-2 inspired interval calculation
    if new_mastery >= 0.9:
        interval = stability * 2.5
    elif new_mastery >= 0.6:
        interval = stability * 1.5
    else:
        interval = max(1, stability * 0.5)

    next_review = now + timedelta(days=interval)
    new_stability = stability * (1 + 0.1 * new_mastery)

    # Update in same transaction block
    with engine.begin() as conn:
        from sqlalchemy import text

        conn.execute(
            text("""
                UPDATE concept_mastery
                SET mastery = :mastery, stability = :stability,
                    review_count = :review_count, last_practiced = :now,
                    next_review = :next_review, updated_at = :now
                WHERE user_id = :uid AND concept_id = :cid
            """),
            {
                "mastery": new_mastery,
                "stability": new_stability,
                "review_count": review_count + 1,
                "now": now,
                "next_review": next_review,
                "uid": user_id,
                "cid": concept_id,
            },
        )
        conn.commit()

    return {
        "success": True,
        "new_mastery": round(new_mastery, 3),
        "next_review": next_review.isoformat(),
        "interval_days": round(interval, 1),
    }


# ── Get Preferences ──────────────────────────────────────────

@tool("get_preferences", args_schema=GetPreferencesInput)
async def get_preferences(user_id: str) -> dict[str, Any]:
    """查询用户偏好（从历史行为推断）。

    返回 {resource_type偏好, language偏好, difficulty偏好, learning_style}。
    """
    from openlearning.database import get_engine

    engine = get_engine()

    # Analyze resource interactions
    with engine.connect() as conn:
        from sqlalchemy import text

        # Resource type preference
        result = conn.execute(
            text("""
                SELECT r.resource_type, COUNT(*) as cnt, AVG(ri.rating) as avg_rating
                FROM resource_interactions ri
                JOIN resources r ON ri.resource_id = r.id
                WHERE ri.user_id = :uid AND ri.action IN ('completed', 'rated', 'bookmarked')
                GROUP BY r.resource_type
                ORDER BY cnt DESC
            """),
            {"uid": user_id},
        ).fetchall()

        type_prefs = {}
        total = sum(row.cnt for row in result) or 1
        for row in result:
            type_prefs[row.resource_type] = round(row.cnt / total, 2)

        # Language preference
        result = conn.execute(
            text("""
                SELECT r.language, COUNT(*) as cnt
                FROM resource_interactions ri
                JOIN resources r ON ri.resource_id = r.id
                WHERE ri.user_id = :uid AND ri.action IN ('completed', 'viewed')
                GROUP BY r.language
                ORDER BY cnt DESC
            """),
            {"uid": user_id},
        ).fetchall()

        lang_prefs = {}
        total = sum(row.cnt for row in result) or 1
        for row in result:
            lang_prefs[row.language] = round(row.cnt / total, 2)

    return {
        "resource_type": type_prefs,
        "language": lang_prefs,
        "difficulty": "intermediate",  # default, can be inferred
        "learning_style": "reading",  # default, can be inferred from type_prefs
    }


# ── Record Event ─────────────────────────────────────────────

@tool("record_event", args_schema=RecordEventInput)
async def record_event(
    user_id: str,
    concept_id: str,
    event: str,
    resource_id: str | None = None,
    score: float | None = None,
    time_spent: int | None = None,
) -> dict[str, Any]:
    """记录学习事件到学习轨迹。

    返回 {success}。
    """
    import uuid

    from openlearning.database import get_engine

    engine = get_engine()

    with engine.connect() as conn:
        from sqlalchemy import text

        conn.execute(
            text("""
                INSERT INTO learning_events (id, user_id, concept_id, event_type, resource_id, score, time_spent)
                VALUES (:id, :uid, :cid, :event, :rid, :score, :time)
            """),
            {
                "id": uuid.uuid4().hex[:12],
                "uid": user_id,
                "cid": concept_id,
                "event": event,
                "rid": resource_id,
                "score": score,
                "time": time_spent,
            },
        )
        conn.commit()

    # Also update mastery
    await update_mastery.ainvoke({
        "user_id": user_id,
        "concept_id": concept_id,
        "event": event,
        "score": score,
        "time_spent": time_spent,
    })

    return {"success": True}


# ── Tools Export ─────────────────────────────────────────────

TOOLS = [get_mastery, update_mastery, get_preferences, record_event]


def get_tools() -> list:
    return list(TOOLS)
