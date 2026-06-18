"""Tests for the Planner Agent."""

from __future__ import annotations

import pytest

from openlearning.agents.planner import (
    _analyze_request,
    _expand_knowledge_graph,
    _generate_search_queries,
    _infer_subtopics,
)


def test_analyze_request_basic():
    analysis = _analyze_request("我想学 Rust 编程", {"level": "beginner", "lang": ["zh", "en"]})
    assert "rust" in analysis["topic"].lower() or "Rust" in analysis["topic"]
    assert analysis["level"] == "beginner"
    assert "zh" in analysis["languages"]


def test_infer_subtopics_rust():
    subs = _infer_subtopics("Rust")
    assert len(subs) > 0
    assert any("ownership" in s.lower() for s in subs)


def test_infer_subtopics_unknown():
    subs = _infer_subtopics("Quantum Entanglement")
    assert len(subs) > 0


def test_expand_knowledge_graph():
    analysis = {
        "topic": "Rust",
        "subtopics": ["ownership", "borrowing"],
        "level": "intermediate",
    }
    graph = _expand_knowledge_graph(analysis)

    assert len(graph["nodes"]) >= 3  # root + 2 subtopics
    assert len(graph["edges"]) >= 2
    assert graph["topic"] == "Rust"


def test_generate_search_queries():
    graph = {
        "nodes": [
            {"id": "rust", "name": "Rust", "type": "concept"},
            {"id": "ownership", "name": "Ownership", "type": "concept"},
        ],
        "edges": [],
        "topic": "Rust",
    }
    analysis = {"topic": "Rust", "languages": ["zh", "en"]}
    queries = _generate_search_queries(graph, analysis, {})

    assert len(queries) > 0
    assert any("Rust" in q for q in queries)
