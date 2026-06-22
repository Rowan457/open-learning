"""Tests for Reflector Agent — strategy reflection logic."""

import pytest
from openlearning.agents.reflector import (
    _reflect,
    _should_continue,
    _find_missing_concepts,
    _find_missing_types,
)


class TestShouldContinue:
    def test_all_passed_stops(self):
        cont, reason = _should_continue(
            all_passed=True, iteration=0, max_iterations=3,
            missing_concepts=[], missing_types=[], quality={}, freshness={},
        )
        assert cont is False
        assert reason == "all_passed"

    def test_max_iterations_stops(self):
        cont, reason = _should_continue(
            all_passed=False, iteration=3, max_iterations=3,
            missing_concepts=["a"], missing_types=[], quality={}, freshness={},
        )
        assert cont is False
        assert reason == "max_iterations_reached"

    def test_missing_concepts_continues(self):
        cont, reason = _should_continue(
            all_passed=False, iteration=0, max_iterations=3,
            missing_concepts=["a", "b"], missing_types=[], quality={}, freshness={},
        )
        assert cont is True
        assert reason == "missing_concepts"

    def test_missing_types_continues(self):
        cont, reason = _should_continue(
            all_passed=False, iteration=0, max_iterations=3,
            missing_concepts=[], missing_types=["video"], quality={}, freshness={},
        )
        assert cont is True
        assert reason == "missing_types"

    def test_low_quality_continues(self):
        cont, reason = _should_continue(
            all_passed=False, iteration=0, max_iterations=3,
            missing_concepts=[], missing_types=[],
            quality={"pass": False}, freshness={"pass": True},
        )
        assert cont is True
        assert reason == "low_quality"


class TestFindMissingConcepts:
    def test_from_coverage(self):
        coverage = {"uncovered": ["Alpha", "Beta"]}
        result = _find_missing_concepts(coverage, {})
        assert result == ["Alpha", "Beta"]

    def test_from_graph_nodes(self):
        coverage = {}
        graph = {"nodes": [{"id": "a", "name": "Alpha"}, {"id": "b", "name": "Beta"}]}
        result = _find_missing_concepts(coverage, graph)
        assert "Alpha" in result or "a" in result


class TestFindMissingTypes:
    def test_all_present(self):
        diversity = {"types": ["article", "video", "paper", "repo"]}
        result = _find_missing_types(diversity)
        assert len(result) == 0

    def test_some_missing(self):
        diversity = {"types": ["article"]}
        result = _find_missing_types(diversity)
        assert "paper" in result
        assert "video" in result or "repo" in result


class TestReflect:
    def test_full_reflection(self):
        evaluation = {
            "pass": False,
            "quality": {"pass": True},
            "coverage": {"pass": False, "uncovered": ["X", "Y"]},
            "diversity": {"types": ["google"]},
            "freshness": {"pass": True},
        }
        result = _reflect(evaluation, {}, {}, iteration=0, max_iterations=3)
        assert result["should_continue"] is True
        assert len(result["missing_concepts"]) > 0
