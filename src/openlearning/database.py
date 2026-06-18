"""Database connection, initialization, and migration."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import SQLModel, create_engine, Session, select

from openlearning.config import get_config
from openlearning.models import (
    Concept,
    ConceptMastery,
    ConceptRelation,
    CrawlTask,
    LearningEvent,
    Project,
    QualityScore,
    Resource,
    ResourceInteraction,
    ResourceTopic,
    Topic,
    Update,
)

# ── Engine ───────────────────────────────────────────────────

_engine = None


def get_engine(url: str | None = None):
    """Get or create the SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is not None and url is None:
        return _engine

    if url is None:
        db_path = Path(get_config().db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path}"

    _engine = create_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    return _engine


def init_db(engine=None) -> None:
    """Create all tables if they don't exist."""
    eng = engine or get_engine()
    SQLModel.metadata.create_all(eng)


def get_session(engine=None) -> Session:
    """Get a new SQLModel session."""
    eng = engine or get_engine()
    return Session(eng)


# ── Convenience helpers ──────────────────────────────────────

def create_project(title: str, description: str = "") -> Project:
    """Create a new learning project."""
    project = Project(title=title, description=description)
    with get_session() as session:
        session.add(project)
        session.commit()
        session.refresh(project)
    return project


def get_project(project_id: str) -> Project | None:
    """Get a project by ID."""
    with get_session() as session:
        return session.get(Project, project_id)


def list_projects() -> list[Project]:
    """List all projects, newest first."""
    from sqlmodel import select

    with get_session() as session:
        statement = select(Project).order_by(Project.updated_at.desc())
        return list(session.exec(statement).all())


def save_resource(resource: Resource) -> Resource:
    """Save or update a resource."""
    with get_session() as session:
        existing = session.exec(
            select(Resource).where(Resource.url == resource.url)
        ).first()
        if existing:
            # Update existing
            for field in resource.model_fields_set:
                setattr(existing, field, getattr(resource, field))
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        else:
            session.add(resource)
            session.commit()
            session.refresh(resource)
            return resource


def get_resources_by_project(project_id: str) -> list[Resource]:
    """Get all resources for a project."""
    from sqlmodel import select

    with get_session() as session:
        statement = (
            select(Resource)
            .where(Resource.project_id == project_id)
            .order_by(Resource.quality_score.desc())
        )
        return list(session.exec(statement).all())


# select is already imported at the top
