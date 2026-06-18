"""Learning trajectory tracker — records learning events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


def record_learning_event(
    user_id: str,
    concept_id: str,
    event_type: str,
    resource_id: str | None = None,
    score: float | None = None,
    time_spent: int | None = None,
) -> dict[str, Any]:
    """Record a learning event to the database.

    Event types: started, practiced, mastered, reviewed, tested
    """
    from openlearning.database import get_engine

    engine = get_engine()
    event_id = uuid.uuid4().hex[:12]

    with engine.connect() as conn:
        from sqlalchemy import text

        conn.execute(
            text("""
                INSERT INTO learning_events (id, user_id, concept_id, event_type, resource_id, score, time_spent)
                VALUES (:id, :uid, :cid, :event, :rid, :score, :time)
            """),
            {
                "id": event_id,
                "uid": user_id,
                "cid": concept_id,
                "event": event_type,
                "rid": resource_id,
                "score": score,
                "time": time_spent,
            },
        )
        conn.commit()

    return {"success": True, "event_id": event_id}


def get_learning_trajectory(user_id: str, concept_id: str) -> list[dict]:
    """Get the learning trajectory for a specific concept."""
    from openlearning.database import get_engine

    engine = get_engine()

    with engine.connect() as conn:
        from sqlalchemy import text

        result = conn.execute(
            text("""
                SELECT event_type, score, time_spent, created_at
                FROM learning_events
                WHERE user_id = :uid AND concept_id = :cid
                ORDER BY created_at ASC
            """),
            {"uid": user_id, "cid": concept_id},
        )
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]
