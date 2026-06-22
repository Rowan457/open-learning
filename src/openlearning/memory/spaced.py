"""Spaced repetition scheduler — SM-2 algorithm implementation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def calculate_next_review(
    mastery: float,
    stability: float = 1.0,
    review_count: int = 0,
) -> dict[str, Any]:
    """Calculate the next review time using SM-2 algorithm.

    Args:
        mastery: Current mastery level (0.0 – 1.0)
        stability: Current stability factor
        review_count: Number of previous reviews

    Returns:
        {next_review: datetime, interval_days: float, new_stability: float}
    """
    # Interval calculation based on mastery
    if mastery >= 0.9:
        interval = stability * 2.5  # Well-known: long interval
    elif mastery >= 0.6:
        interval = stability * 1.5  # Learning: medium interval
    else:
        interval = max(1, stability * 0.5)  # Weak: short interval

    # Stability grows with successful reviews
    new_stability = stability * (1 + 0.1 * mastery)

    # Minimum interval: 1 day
    interval = max(1, interval)

    from datetime import timezone
    next_review = datetime.now(timezone.utc) + timedelta(days=interval)

    return {
        "next_review": next_review,
        "interval_days": round(interval, 1),
        "new_stability": round(new_stability, 3),
    }


def get_due_concepts(user_id: str, limit: int = 10) -> list[dict]:
    """Get concepts that are due for review."""
    from openlearning.database import get_engine

    engine = get_engine()

    with engine.connect() as conn:
        from sqlalchemy import text

        result = conn.execute(
            text("""
                SELECT cm.concept_id, c.name, cm.mastery, cm.stability, cm.next_review
                FROM concept_mastery cm
                JOIN concepts c ON cm.concept_id = c.id
                WHERE cm.user_id = :uid
                  AND cm.next_review <= datetime('now')
                ORDER BY cm.stability ASC
                LIMIT :limit
            """),
            {"uid": user_id, "limit": limit},
        )
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]
