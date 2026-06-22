"""Tests for Memory Skill — mastery tracking and spaced repetition."""

import pytest
import asyncio
from datetime import datetime


def _run(coro):
    """Run async function in sync test."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestUpdateMastery:
    """Test update_mastery with real in-memory database."""

    def test_started_event(self, engine):
        from openlearning.skills.memory import update_mastery
        result = _run(update_mastery.ainvoke({
            "user_id": "test", "concept_id": "test_concept", "event": "started",
        }))
        assert result["success"] is True
        assert result["new_mastery"] == pytest.approx(0.1, abs=0.01)
        assert "next_review" in result

    def test_mastered_event(self, engine):
        from openlearning.skills.memory import update_mastery
        _run(update_mastery.ainvoke({"user_id": "test", "concept_id": "c1", "event": "started"}))
        result = _run(update_mastery.ainvoke({"user_id": "test", "concept_id": "c1", "event": "mastered"}))
        assert result["new_mastery"] == pytest.approx(0.5, abs=0.01)

    def test_mastery_caps_at_1(self, engine):
        from openlearning.skills.memory import update_mastery
        for _ in range(20):
            result = _run(update_mastery.ainvoke({"user_id": "test", "concept_id": "c2", "event": "mastered"}))
        assert result["new_mastery"] <= 1.0

    def test_interval_increases_with_mastery(self, engine):
        from openlearning.skills.memory import update_mastery
        r1 = _run(update_mastery.ainvoke({"user_id": "test", "concept_id": "c3", "event": "started"}))
        r2 = _run(update_mastery.ainvoke({"user_id": "test", "concept_id": "c3", "event": "mastered"}))
        assert r2["interval_days"] >= r1["interval_days"]


class TestGetMastery:
    def test_returns_records(self, engine):
        from openlearning.skills.memory import get_mastery, update_mastery
        from sqlalchemy import text
        # Insert a concept so the JOIN works
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO concepts (id, name, type, importance, created_at) VALUES ('c1', 'Test', 'concept', 0.5, '2026-01-01')"))
        _run(update_mastery.ainvoke({"user_id": "test", "concept_id": "c1", "event": "started"}))
        result = _run(get_mastery.ainvoke({"user_id": "test"}))
        assert len(result) >= 1
        assert any(m["concept_id"] == "c1" for m in result)

    def test_empty_for_unknown_user(self, engine):
        from openlearning.skills.memory import get_mastery
        result = _run(get_mastery.ainvoke({"user_id": "nonexistent"}))
        assert result == []


class TestRecordEvent:
    def test_records_and_updates(self, engine):
        from openlearning.skills.memory import record_event, get_mastery
        from sqlalchemy import text
        # Insert a concept so the JOIN works
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO concepts (id, name, type, importance, created_at) VALUES ('c1', 'Test', 'concept', 0.5, '2026-01-01')"))
        result = _run(record_event.ainvoke({"user_id": "test", "concept_id": "c1", "event": "started"}))
        assert result["success"] is True
        mastery = _run(get_mastery.ainvoke({"user_id": "test"}))
        assert len(mastery) >= 1
