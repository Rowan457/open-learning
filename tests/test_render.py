"""Tests for Render Skill — static site generation."""

import pytest
import asyncio
import tempfile
from pathlib import Path


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestBuildLearningSystem:
    def test_generates_all_pages(self):
        from openlearning.skills.render import build_learning_system

        graph = {
            "nodes": [
                {"id": "a", "name": "Alpha", "type": "concept", "difficulty": "beginner", "importance": 0.8,
                 "definition": "Alpha def", "explanation": "Some explanation", "key_points": ["p1", "p2"],
                 "examples": ["e1"], "common_mistakes": [], "learning_tips": "Try it"},
                {"id": "b", "name": "Beta", "type": "technology", "difficulty": "intermediate", "importance": 0.5},
            ],
            "edges": [{"from": "a", "to": "b", "type": "prerequisite", "weight": 0.9, "reason": "A is prereq of B"}],
            "topic": "Test",
        }
        path = {"steps": [{"concept": "a", "action": "learn"}, {"concept": "b", "action": "learn"}]}

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run(build_learning_system.ainvoke({
                "knowledge_graph": graph, "learning_path": path,
                "knowledge_resources": {}, "output_dir": tmpdir,
            }))
            assert result["pages_generated"] >= 6
            assert Path(tmpdir, "index.html").exists()
            assert Path(tmpdir, "graph.html").exists()
            assert Path(tmpdir, "learning-path.html").exists()
            assert Path(tmpdir, "bookmarks.html").exists()
            assert Path(tmpdir, "knowledge", "a.html").exists()
            assert Path(tmpdir, "knowledge", "b.html").exists()
            assert Path(tmpdir, "data", "knowledge-graph.json").exists()

    def test_concept_page_has_rich_content(self):
        from openlearning.skills.render import build_learning_system

        graph = {
            "nodes": [{"id": "x", "name": "Test Node", "type": "concept", "difficulty": "beginner",
                        "importance": 0.7, "definition": "A test concept", "explanation": "Detailed explanation here",
                        "key_points": ["point 1"], "examples": ["example 1"], "common_mistakes": ["mistake 1"],
                        "learning_tips": "Keep practicing"}],
            "edges": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            _run(build_learning_system.ainvoke({"knowledge_graph": graph, "output_dir": tmpdir}))
            content = Path(tmpdir, "knowledge", "x.html").read_text(encoding="utf-8")
            assert "A test concept" in content
            assert "Detailed explanation" in content
            assert "point 1" in content
            assert "example 1" in content
            assert "mistake 1" in content
            assert "Keep practicing" in content

    def test_empty_graph(self):
        from openlearning.skills.render import build_learning_system

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run(build_learning_system.ainvoke({
                "knowledge_graph": {"nodes": [], "edges": []}, "output_dir": tmpdir,
            }))
            assert result["pages_generated"] >= 4
