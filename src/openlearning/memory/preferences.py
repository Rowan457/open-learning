"""User preference learning — infer preferences from interaction history."""

from __future__ import annotations

from typing import Any


def infer_preferences(interactions: list[dict]) -> dict[str, Any]:
    """Infer user preferences from resource interactions.

    Analyzes: resource type, language, difficulty, learning style.
    """
    if not interactions:
        return {
            "resource_type": {},
            "language": {"zh": 0.5, "en": 0.5},
            "difficulty": "intermediate",
            "learning_style": "reading",
        }

    # Resource type preference
    type_counts: dict[str, int] = {}
    for i in interactions:
        rtype = i.get("resource_type", "article")
        action = i.get("action", "viewed")
        weight = {"completed": 3, "rated": 2, "bookmarked": 2, "viewed": 1}.get(action, 1)
        type_counts[rtype] = type_counts.get(rtype, 0) + weight

    total_weight = sum(type_counts.values()) or 1
    type_prefs = {k: round(v / total_weight, 2) for k, v in type_counts.items()}

    # Language preference
    lang_counts: dict[str, int] = {}
    for i in interactions:
        lang = i.get("language", "en")
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    total_lang = sum(lang_counts.values()) or 1
    lang_prefs = {k: round(v / total_lang, 2) for k, v in lang_counts.items()}

    # Learning style (inferred from type preferences)
    if type_prefs.get("video", 0) > 0.4:
        style = "visual"
    elif type_prefs.get("repo", 0) > 0.3:
        style = "hands-on"
    else:
        style = "reading"

    return {
        "resource_type": type_prefs,
        "language": lang_prefs,
        "difficulty": "intermediate",
        "learning_style": style,
    }
