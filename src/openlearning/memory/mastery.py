"""Concept mastery calculation — multi-dimensional signal aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def calculate_mastery(
    resource_completion: float = 0.0,
    quiz_score: float = 0.0,
    time_spent: float = 0.0,
    recency_days: float = 365.0,
    review_count: int = 0,
    self_report: float = 0.0,
) -> float:
    """Calculate concept mastery (0.0 – 1.0) from multiple signals.

    Signals:
        resource_completion: 0-1, ratio of completed resources
        quiz_score: 0-1, normalized quiz/test score
        time_spent: minutes spent learning (normalized)
        recency_days: days since last learning activity
        review_count: number of review sessions
        self_report: 0-1, user's self-assessment
    """
    signals = {
        "resource_completion": (resource_completion, 0.30),
        "quiz_score": (quiz_score, 0.25),
        "time_spent": (min(time_spent / 120, 1.0), 0.15),  # normalize to 2 hours
        "recency": (max(0, 1 - recency_days / 365), 0.15),  # decay over 1 year
        "review_count": (min(review_count / 5, 1.0), 0.10),  # cap at 5 reviews
        "self_report": (self_report, 0.05),
    }

    score = sum(value * weight for value, weight in signals.values())
    return max(0.0, min(1.0, score))


def schedule_review(
    mastery: float,
    stability: float = 1.0,
) -> dict[str, Any]:
    """Schedule next review based on SM-2 algorithm.

    Returns:
        {next_review_days, stability}
    """
    if mastery >= 0.9:
        interval = stability * 2.5
    elif mastery >= 0.6:
        interval = stability * 1.5
    else:
        interval = max(1, stability * 0.5)

    new_stability = stability * (1 + 0.1 * mastery)

    return {
        "next_review_days": round(interval, 1),
        "stability": round(new_stability, 3),
    }


def decay_mastery(mastery: float, days_since_practice: int) -> float:
    """Apply time-based mastery decay (forgetting curve)."""
    # Ebbinghaus forgetting curve approximation
    import math

    decay = math.exp(-days_since_practice / 30)  # 30-day half-life
    return mastery * decay
