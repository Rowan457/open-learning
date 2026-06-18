"""Knowledge gap analysis — compare knowledge graph vs mastery."""

from __future__ import annotations

from typing import Any


def analyze_knowledge_gaps(
    knowledge_graph: dict,
    mastery_list: list[dict],
) -> list[dict[str, Any]]:
    """Find knowledge gaps by comparing graph nodes vs mastery data.

    Returns list of uncovered concepts with their importance.
    """
    nodes = knowledge_graph.get("nodes", [])
    if not nodes:
        return []

    # Build mastery lookup
    mastery_map = {}
    for m in mastery_list:
        mastery_map[m.get("concept_id", "")] = m.get("mastery", 0.0)

    gaps = []
    for node in nodes:
        node_id = node.get("id", "")
        current_mastery = mastery_map.get(node_id, 0.0)

        if current_mastery < 0.5:  # Gap threshold
            gaps.append({
                "concept_id": node_id,
                "name": node.get("name", ""),
                "type": node.get("type", "concept"),
                "importance": node.get("importance", 0.5),
                "current_mastery": current_mastery,
                "priority": node.get("importance", 0.5) * (1 - current_mastery),
            })

    # Sort by priority (high importance × low mastery)
    gaps.sort(key=lambda g: g["priority"], reverse=True)

    return gaps
