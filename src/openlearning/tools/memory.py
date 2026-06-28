"""Memory Skill — user memory operations.

Tools: get_mastery, update_mastery, get_preferences, record_event
"""

from __future__ import annotations

from datetime import datetime, timezone
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

    基于学习事件，使用多维度加权计算掌握度（含遗忘衰减）。
    返回 {success, new_mastery, next_review}。
    """
    from datetime import timedelta

    from openlearning.database import get_engine
    from openlearning.memory.mastery import calculate_mastery, decay_mastery, schedule_review

    engine = get_engine()
    now = datetime.now(timezone.utc)

    # Single transaction for read + calculate + write
    with engine.begin() as conn:
        from sqlalchemy import text

        result = conn.execute(
            text("SELECT * FROM concept_mastery WHERE user_id = :uid AND concept_id = :cid"),
            {"uid": user_id, "cid": concept_id},
        ).fetchone()

        if result:
            current_mastery = result.mastery or 0.0
            stability = result.stability or 1.0
            review_count = result.review_count or 0
            last_practiced = result.last_practiced
        else:
            current_mastery = 0.0
            stability = 1.0
            review_count = 0
            last_practiced = None
            conn.execute(
                text("""
                    INSERT INTO concept_mastery (id, user_id, concept_id, mastery, stability, review_count, learned_at, updated_at)
                    VALUES (:id, :uid, :cid, 0.0, 1.0, 0, :now, :now)
                """),
                {"id": f"{user_id}_{concept_id}", "uid": user_id, "cid": concept_id, "now": now},
            )

        # 1. 遗忘衰减：根据距上次学习的天数衰减当前掌握度
        if last_practiced:
            days_since = (now - last_practiced).days
            decayed_mastery = decay_mastery(current_mastery, days_since)
        else:
            decayed_mastery = current_mastery

        # 2. 从事件中提取多维度信号
        # 事件类型映射到信号强度
        event_signals = {
            "started":    {"resource_completion": 0.2, "recency_days": 0},
            "practiced":  {"resource_completion": 0.5, "recency_days": 0},
            "mastered":   {"resource_completion": 1.0, "recency_days": 0},
            "reviewed":   {"recency_days": 0},
            "tested":     {"recency_days": 0},
        }
        signals = event_signals.get(event, {"recency_days": 0})

        # 3. 多维度加权计算新掌握度
        new_mastery = calculate_mastery(
            resource_completion=signals.get("resource_completion", decayed_mastery),
            quiz_score=(score / 100.0) if score is not None else 0.0,
            time_spent=float(time_spent) if time_spent else 0.0,
            recency_days=signals.get("recency_days", 0),
            review_count=review_count + 1,
            self_report=0.0,
        )

        # 4. 取衰减值和新计算值的较高者（避免单次学习导致掌握度下降）
        new_mastery = max(decayed_mastery, new_mastery)
        new_mastery = min(1.0, max(0.0, new_mastery))

        # 5. SM-2 间隔重复调度
        review = schedule_review(new_mastery, stability)
        interval = review["next_review_days"]
        new_stability = review["stability"]
        next_review = now + timedelta(days=interval)

        # Write in same transaction
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

    # Infer difficulty and learning_style from interaction data
    difficulty = "intermediate"
    learning_style = "reading"

    # Infer learning style from resource type preferences
    if type_prefs:
        top_type = max(type_prefs, key=type_prefs.get)
        style_map = {"video": "visual", "repo": "hands-on", "paper": "reading", "article": "reading"}
        learning_style = style_map.get(top_type, "reading")

    # Try to infer difficulty from memory module
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("""
                SELECT AVG(CASE WHEN r.difficulty = 'beginner' THEN 1
                                WHEN r.difficulty = 'intermediate' THEN 2
                                WHEN r.difficulty = 'advanced' THEN 3
                                ELSE 2 END) as avg_diff
                FROM resource_interactions ri
                JOIN resources r ON ri.resource_id = r.id
                WHERE ri.user_id = :uid AND ri.action IN ('completed', 'rated')
            """), {"uid": user_id}).fetchone()
            if result and result.avg_diff:
                avg = result.avg_diff
                if avg < 1.5:
                    difficulty = "beginner"
                elif avg < 2.5:
                    difficulty = "intermediate"
                else:
                    difficulty = "advanced"
    except Exception:
        pass

    return {
        "resource_type": type_prefs,
        "language": lang_prefs,
        "difficulty": difficulty,
        "learning_style": learning_style,
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

    with engine.begin() as conn:
        from sqlalchemy import text

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            text("""
                INSERT INTO learning_events (id, user_id, concept_id, event_type, resource_id, score, time_spent, created_at)
                VALUES (:id, :uid, :cid, :event, :rid, :score, :time, :now)
            """),
            {
                "id": uuid.uuid4().hex[:12],
                "uid": user_id,
                "cid": concept_id,
                "event": event,
                "rid": resource_id,
                "score": score,
                "time": time_spent,
                "now": now,
            },
        )

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
