"""Tests for Collector Agent — deduplication logic."""

import pytest
from openlearning.agents.collector import _deduplicate, _is_chinese


class TestDeduplicate:
    def test_removes_exact_urls(self):
        resources = [
            {"url": "https://example.com/a", "title": "A"},
            {"url": "https://example.com/a", "title": "A dup"},
            {"url": "https://example.com/b", "title": "B"},
        ]
        result = _deduplicate(resources, set())
        assert len(result) == 2
        assert result[0]["title"] == "A"
        assert result[1]["title"] == "B"

    def test_normalizes_urls(self):
        resources = [
            {"url": "https://example.com/a/", "title": "A"},
            {"url": "https://example.com/a?foo=bar", "title": "A with params"},
            {"url": "https://example.com/a#section", "title": "A with hash"},
        ]
        result = _deduplicate(resources, set())
        assert len(result) == 1

    def test_avoid_set(self):
        resources = [
            {"url": "https://example.com/a", "title": "A"},
            {"url": "https://example.com/b", "title": "B"},
        ]
        avoid = {"https://example.com/a"}
        result = _deduplicate(resources, avoid)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/b"

    def test_skips_no_url(self):
        resources = [
            {"url": "", "title": "No URL"},
            {"url": "https://example.com/a", "title": "A"},
        ]
        result = _deduplicate(resources, set())
        assert len(result) == 1

    def test_empty_input(self):
        result = _deduplicate([], set())
        assert result == []


class TestIsChinese:
    def test_chinese_text(self):
        assert _is_chinese("学习Agent") is True

    def test_english_text(self):
        assert _is_chinese("learn Rust") is False

    def test_mixed(self):
        assert _is_chinese("Python 教程") is True
