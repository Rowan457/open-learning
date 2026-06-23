"""Tests for multi-project management database functions."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Provide a transactional database session."""
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def mock_db(db_engine):
    """Mock the database engine for all database functions."""
    with patch("openlearning.database.get_engine", return_value=db_engine):
        with patch("openlearning.database._engine", db_engine):
            yield db_engine


# ── Project CRUD ────────────────────────────────────────────


class TestProjectManagement:
    def test_create_and_get(self, mock_db):
        from openlearning.database import create_project, get_project, init_db

        init_db(engine=mock_db)
        project = create_project("Test Project", "A test project")
        assert project.title == "Test Project"

        fetched = get_project(project.id)
        assert fetched is not None
        assert fetched.title == "Test Project"

    def test_update_project(self, mock_db):
        from openlearning.database import create_project, init_db, update_project

        init_db(engine=mock_db)
        project = create_project("Original Title", "Original desc")

        updated = update_project(project.id, title="New Title")
        assert updated is not None
        assert updated.title == "New Title"
        assert updated.description == "Original desc"  # unchanged

    def test_update_project_status(self, mock_db):
        from openlearning.database import create_project, init_db, update_project

        init_db(engine=mock_db)
        project = create_project("Test")

        updated = update_project(project.id, status="archived")
        assert updated is not None
        assert updated.status == "archived"

    def test_update_nonexistent(self, mock_db):
        from openlearning.database import init_db, update_project

        init_db(engine=mock_db)
        result = update_project("nonexistent", title="New")
        assert result is None

    def test_delete_project(self, mock_db):
        from openlearning.database import create_project, delete_project, get_project, init_db

        init_db(engine=mock_db)
        project = create_project("To Delete")

        result = delete_project(project.id)
        assert result is True

        fetched = get_project(project.id)
        assert fetched is None

    def test_delete_nonexistent(self, mock_db):
        from openlearning.database import delete_project, init_db

        init_db(engine=mock_db)
        result = delete_project("nonexistent")
        assert result is False

    def test_list_projects(self, mock_db):
        from openlearning.database import create_project, init_db, list_projects

        init_db(engine=mock_db)
        create_project("Project A")
        create_project("Project B")
        create_project("Project C")

        projects = list_projects()
        assert len(projects) == 3
        # Should be ordered by updated_at desc
        titles = [p.title for p in projects]
        assert "Project C" in titles


# ── Project Stats ───────────────────────────────────────────


class TestProjectStats:
    def test_get_stats_empty(self, mock_db):
        from openlearning.database import create_project, get_project_stats, init_db

        init_db(engine=mock_db)
        project = create_project("Empty Project")

        stats = get_project_stats(project.id)
        assert stats["resource_count"] == 0
        assert stats["avg_score"] == 0

    def test_get_stats_nonexistent(self, mock_db):
        from openlearning.database import get_project_stats, init_db

        init_db(engine=mock_db)
        stats = get_project_stats("nonexistent")
        assert stats == {}

    def test_list_projects_with_stats(self, mock_db):
        from openlearning.database import create_project, init_db, list_projects_with_stats

        init_db(engine=mock_db)
        create_project("Project A")
        create_project("Project B")

        result = list_projects_with_stats()
        assert len(result) == 2
        assert all("resource_count" in s for s in result)
        assert all("avg_score" in s for s in result)


# ── Archive/Activate Flow ───────────────────────────────────


class TestArchiveFlow:
    def test_archive_and_activate(self, mock_db):
        from openlearning.database import (
            create_project,
            get_project,
            init_db,
            update_project,
        )

        init_db(engine=mock_db)
        project = create_project("Archivable")

        # Archive
        archived = update_project(project.id, status="archived")
        assert archived.status == "archived"

        # Activate
        activated = update_project(project.id, status="active")
        assert activated.status == "active"

    def test_archive_preserves_data(self, mock_db):
        from openlearning.database import (
            create_project,
            get_project_stats,
            init_db,
            update_project,
        )

        init_db(engine=mock_db)
        project = create_project("With Data")
        # In a real test, we'd add resources here

        update_project(project.id, status="archived")
        stats = get_project_stats(project.id)
        assert stats["title"] == "With Data"  # data preserved
