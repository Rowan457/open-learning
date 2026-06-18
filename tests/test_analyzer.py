"""Tests for the Analyzer Agent and Analyze Skill."""

from __future__ import annotations

import pytest

from openlearning.skills.analyze import _rule_score


def test_rule_score_basic():
    content = "# Test Article\n\nThis is a test with some code:\n```python\nprint('hello')\n```\n\nMore content here."
    metadata = {"source": "google", "published": "2025-01-01"}

    scores = _rule_score(content, metadata)

    assert "authority" in scores
    assert "richness" in scores
    assert "freshness" in scores
    assert "community" in scores
    assert "structure" in scores

    # All scores should be 0-10
    for v in scores.values():
        assert 0 <= v <= 10


def test_rule_score_arxiv():
    content = "Abstract: This paper presents..."
    metadata = {"source": "arxiv"}

    scores = _rule_score(content, metadata)
    assert scores["authority"] >= 8.0  # arxiv is authoritative


def test_rule_score_github_stars():
    content = "A popular repository"
    metadata = {"source": "github", "stars": 15000}

    scores = _rule_score(content, metadata)
    assert scores["authority"] >= 8.0
    assert scores["community"] >= 8.0


def test_rule_score_freshness():
    content = "Some content"

    # Recent
    scores_recent = _rule_score(content, {"published": "2026-01-01"})
    assert scores_recent["freshness"] >= 8.0

    # Old
    scores_old = _rule_score(content, {"published": "2020-01-01"})
    assert scores_old["freshness"] <= 4.0
