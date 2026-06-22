"""Tests for Evaluator Engine — rule-based quality/coverage/diversity/freshness checks."""

import pytest
from openlearning.agents.evaluator import (
    _check_quality,
    _check_coverage,
    _check_diversity,
    _check_freshness,
)


class TestCheckQuality:
    def test_passing_quality(self):
        resources = [{"quality_score": 7.0}, {"quality_score": 6.0}, {"quality_score": 5.0}]
        result = _check_quality(resources, min_avg=5.0, min_single=3.0)
        assert result["pass"] is True
        assert result["avg"] == 6.0
        assert result["low_count"] == 0

    def test_failing_low_avg(self):
        resources = [{"quality_score": 3.0}, {"quality_score": 4.0}]
        result = _check_quality(resources, min_avg=5.0, min_single=3.0)
        assert result["pass"] is False
        assert result["avg"] == 3.5

    def test_failing_too_many_low(self):
        resources = [
            {"quality_score": 8.0}, {"quality_score": 2.0}, {"quality_score": 2.0},
            {"quality_score": 2.0}, {"quality_score": 2.0},
        ]
        result = _check_quality(resources, min_avg=5.0, min_single=3.0)
        assert result["pass"] is False  # 80% below threshold > 15%

    def test_empty_resources(self):
        result = _check_quality([])
        assert result["pass"] is False
        assert result["avg"] == 0.0


class TestCheckCoverage:
    def test_full_coverage(self):
        graph = {"nodes": [{"id": "a", "name": "Alpha"}, {"id": "b", "name": "Beta"}]}
        resources = [{"title": "Alpha guide", "snippet": "alpha stuff"}, {"title": "Beta tutorial", "snippet": "beta stuff"}]
        result = _check_coverage(graph, resources)
        assert result["pass"] is True
        assert result["covered"] == 2

    def test_partial_coverage(self):
        graph = {"nodes": [{"id": "a", "name": "Alpha"}, {"id": "b", "name": "Beta"}, {"id": "c", "name": "Gamma"}]}
        resources = [{"title": "Alpha guide", "snippet": "alpha stuff"}]
        result = _check_coverage(graph, resources)
        assert result["covered"] == 1
        assert result["total"] == 3
        assert result["pass"] is False  # 33% < 60%

    def test_empty_graph(self):
        result = _check_coverage({"nodes": []}, [])
        assert result["pass"] is True


class TestCheckDiversity:
    def test_enough_types(self):
        resources = [
            {"source": "google"}, {"source": "arxiv"}, {"source": "github"},
        ]
        result = _check_diversity(resources, min_types=3)
        assert result["pass"] is True
        assert result["count"] == 3

    def test_not_enough_types(self):
        resources = [{"source": "google"}, {"source": "google"}]
        result = _check_diversity(resources, min_types=3)
        assert result["pass"] is False

    def test_empty(self):
        result = _check_diversity([])
        assert result["pass"] is False


class TestCheckFreshness:
    def test_recent_resources(self):
        resources = [{"published": "2026-01-01"}, {"published": "2025-06-01"}]
        result = _check_freshness(resources, min_recent_ratio=0.2)
        assert result["pass"] is True
        assert result["recent_count"] == 2

    def test_old_resources(self):
        resources = [{"published": "2020-01-01"}, {"published": "2019-06-01"}]
        result = _check_freshness(resources, min_recent_ratio=0.2)
        assert result["pass"] is False

    def test_mixed(self):
        resources = [{"published": "2026-01-01"}, {"published": "2020-01-01"}]
        result = _check_freshness(resources, min_recent_ratio=0.2)
        assert result["pass"] is True
        assert result["recent_count"] == 1
        assert result["old_count"] == 1

    def test_no_dates(self):
        resources = [{"title": "no date"}]
        result = _check_freshness(resources)
        assert result["pass"] is True  # Unknown dates assume fresh
