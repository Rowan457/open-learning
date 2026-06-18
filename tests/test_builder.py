"""Tests for the Builder Agent."""

from __future__ import annotations

import pytest

from openlearning.agents.builder import _topological_sort, _generate_learning_path


def test_topological_sort_basic():
    nodes = [
        {"id": "a", "name": "A"},
        {"id": "b", "name": "B"},
        {"id": "c", "name": "C"},
    ]
    edges = [
        {"from": "a", "to": "b", "type": "prerequisite"},
        {"from": "b", "to": "c", "type": "prerequisite"},
    ]

    order = _topological_sort(nodes, edges)
    assert order.index("a") < order.index("b")
    assert order.index("b") < order.index("c")


def test_topological_sort_no_edges():
    nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    order = _topological_sort(nodes, [])
    assert len(order) == 3


def test_generate_learning_path_empty():
    graph = {"nodes": [], "edges": []}
    path = _generate_learning_path(graph, {})
    assert path["total_steps"] == 0


def test_generate_learning_path_with_mastery():
    graph = {
        "nodes": [
            {"id": "a", "name": "A", "importance": 0.9},
            {"id": "b", "name": "B", "importance": 0.8},
            {"id": "c", "name": "C", "importance": 0.7},
        ],
        "edges": [
            {"from": "a", "to": "b", "type": "prerequisite"},
            {"from": "b", "to": "c", "type": "prerequisite"},
        ],
    }
    memory = {
        "mastery": {
            "mastered": [{"concept_id": "a"}],
            "learning": [],
            "not_started": [],
            "due_reviews": [],
        }
    }

    path = _generate_learning_path(graph, memory)
    # 'a' should be skipped (mastered)
    concept_ids = [s["concept"] for s in path["steps"]]
    assert "a" not in concept_ids
    assert "b" in concept_ids
    assert "c" in concept_ids
    assert path["skipped"] == 1
