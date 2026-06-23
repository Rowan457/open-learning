"""Tests for Updater Agent — change detection logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from openlearning.agents.updater import UpdateReport, check_updates


class TestUpdateReport:
    def test_to_dict(self):
        report = UpdateReport(new=2, updated=1, removed=0, unchanged=5, errors=1)
        d = report.to_dict()
        assert d["new"] == 2
        assert d["updated"] == 1
        assert d["removed"] == 0
        assert d["unchanged"] == 5
        assert d["errors"] == 1
        assert d["total_checked"] == 9

    def test_summary(self):
        report = UpdateReport(new=3, updated=2, removed=1, unchanged=10)
        s = report.summary()
        assert "新增 3" in s
        assert "更新 2" in s
        assert "失效 1" in s
        assert "无变化 10" in s

    def test_summary_no_changes(self):
        report = UpdateReport(unchanged=5)
        s = report.summary()
        assert s == "无变化 5"


class TestCheckUpdates:
    @pytest.mark.asyncio
    async def test_empty_project(self, engine, monkeypatch):
        """No resources → empty report."""
        from openlearning.database import create_project
        from openlearning import database

        monkeypatch.setattr(database, "get_engine", lambda url=None: engine)

        project = create_project(title="Test", description="test")
        report = await check_updates(project.id)
        assert report.new == 0
        assert report.updated == 0
        assert report.unchanged == 0

    @pytest.mark.asyncio
    async def test_content_change_detected(self, engine, session, monkeypatch):
        """When fetch returns different hash, report updated."""
        from openlearning.database import create_project
        from openlearning import database
        from openlearning.models import Resource

        monkeypatch.setattr(database, "get_engine", lambda url=None: engine)

        project = create_project(title="Test", description="test")
        resource = Resource(
            project_id=project.id,
            url="https://example.com/article",
            title="Test Article",
            source="google",
            resource_type="article",
            content_hash="old_hash_abc",
        )
        session.add(resource)
        session.commit()
        session.refresh(resource)

        # Mock fetch_page tool at the module level
        mock_result = {
            "url": "https://example.com/article",
            "title": "Test Article",
            "content": "New content here",
            "content_hash": "new_hash_xyz",
            "success": True,
        }
        mock_tool = AsyncMock()
        mock_tool.ainvoke.return_value = mock_result

        with patch("openlearning.agents.updater.fetch_page", mock_tool):
            report = await check_updates(project.id)

        assert report.updated == 1
        assert report.unchanged == 0

    @pytest.mark.asyncio
    async def test_no_change_detected(self, engine, session, monkeypatch):
        """When fetch returns same hash, report unchanged."""
        from openlearning.database import create_project
        from openlearning import database
        from openlearning.models import Resource

        monkeypatch.setattr(database, "get_engine", lambda url=None: engine)

        project = create_project(title="Test", description="test")
        resource = Resource(
            project_id=project.id,
            url="https://example.com/stable",
            title="Stable Article",
            source="google",
            resource_type="article",
            content_hash="same_hash",
        )
        session.add(resource)
        session.commit()

        mock_result = {
            "url": "https://example.com/stable",
            "title": "Stable Article",
            "content": "Same content",
            "content_hash": "same_hash",
            "success": True,
        }
        mock_tool = AsyncMock()
        mock_tool.ainvoke.return_value = mock_result

        with patch("openlearning.agents.updater.fetch_page", mock_tool):
            report = await check_updates(project.id)

        assert report.unchanged == 1
        assert report.updated == 0


class TestSinceDaysHelpers:
    def test_since_iso(self):
        from openlearning.skills.search import _since_iso
        result = _since_iso(7)
        assert len(result) == 10  # YYYY-MM-DD
        assert result[4] == "-"
        assert result[7] == "-"

    def test_since_yyyymmdd(self):
        from openlearning.skills.search import _since_yyyymmdd
        result = _since_yyyymmdd(30)
        assert len(result) == 8  # YYYYMMDD
        assert result.isdigit()

    def test_since_date_recent(self):
        from openlearning.skills.search import _since_date
        from datetime import datetime, timezone
        dt = _since_date(1)
        now = datetime.now(timezone.utc)
        assert (now - dt).total_seconds() < 86400 + 60  # ~1 day
