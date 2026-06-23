"""Database connection, initialization, and migration."""

from __future__ import annotations

from datetime import datetime
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


# ── Update tracking helpers ──────────────────────────────────


def record_update(
    resource_id: str,
    change_type: str,
    old_hash: str | None = None,
    new_hash: str | None = None,
) -> Update:
    """Record a resource change in the updates table."""
    update = Update(
        resource_id=resource_id,
        change_type=change_type,
        old_hash=old_hash,
        new_hash=new_hash,
    )
    with get_session() as session:
        session.add(update)
        session.commit()
        session.refresh(update)
    return update


def get_updates_since(project_id: str, since: datetime) -> list[Update]:
    """Get all updates for a project since a given datetime."""
    with get_session() as session:
        statement = (
            select(Update)
            .join(Resource, Update.resource_id == Resource.id)
            .where(Resource.project_id == project_id)
            .where(Update.detected_at >= since)
            .order_by(Update.detected_at.desc())
        )
        return list(session.exec(statement).all())


def get_update_summary(project_id: str, since: datetime | None = None) -> dict:
    """Aggregate update counts by change_type."""
    with get_session() as session:
        statement = (
            select(Update)
            .join(Resource, Update.resource_id == Resource.id)
            .where(Resource.project_id == project_id)
        )
        if since:
            statement = statement.where(Update.detected_at >= since)
        updates = list(session.exec(statement).all())

    summary = {"new": 0, "updated": 0, "removed": 0}
    for u in updates:
        if u.change_type in summary:
            summary[u.change_type] += 1
    return summary


def get_existing_urls(project_id: str) -> set[str]:
    """Get all existing resource URLs for a project (for dedup)."""
    with get_session() as session:
        statement = select(Resource.url).where(Resource.project_id == project_id)
        return set(session.exec(statement).all())


def get_last_crawl_date(project_id: str) -> datetime | None:
    """Get the most recent completed crawl timestamp for a project."""
    with get_session() as session:
        statement = (
            select(CrawlTask.completed_at)
            .where(CrawlTask.project_id == project_id)
            .where(CrawlTask.status == "done")
            .order_by(CrawlTask.completed_at.desc())
            .limit(1)
        )
        result = session.exec(statement).first()
        return result


def record_crawl_task(
    project_id: str, query: str, source: str, result_count: int = 0
) -> CrawlTask:
    """Record a completed crawl task."""
    task = CrawlTask(
        project_id=project_id,
        query=query,
        source=source,
        status="done",
        result_count=result_count,
        completed_at=datetime.utcnow(),
    )
    with get_session() as session:
        session.add(task)
        session.commit()
        session.refresh(task)


# ── Multi-project management ────────────────────────────────


def update_project(
    project_id: str,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> Project | None:
    """Update project fields. Returns None if not found."""
    with get_session() as session:
        project = session.get(Project, project_id)
        if not project:
            return None
        if title is not None:
            project.title = title
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        project.updated_at = datetime.utcnow()
        session.add(project)
        session.commit()
        session.refresh(project)
        return project


def delete_project(project_id: str) -> bool:
    """Delete a project and all its resources. Returns True if deleted."""
    with get_session() as session:
        project = session.get(Project, project_id)
        if not project:
            return False
        # Delete related resources
        resources = session.exec(
            select(Resource).where(Resource.project_id == project_id)
        ).all()
        for r in resources:
            # Delete quality scores for this resource
            scores = session.exec(
                select(QualityScore).where(QualityScore.resource_id == r.id)
            ).all()
            for s in scores:
                session.delete(s)
            # Delete updates for this resource
            updates = session.exec(
                select(Update).where(Update.resource_id == r.id)
            ).all()
            for u in updates:
                session.delete(u)
            session.delete(r)

        # Delete crawl tasks
        tasks = session.exec(
            select(CrawlTask).where(CrawlTask.project_id == project_id)
        ).all()
        for t in tasks:
            session.delete(t)

        session.delete(project)
        session.commit()
        return True


def get_project_stats(project_id: str) -> dict:
    """Get aggregated stats for a project."""
    with get_session() as session:
        project = session.get(Project, project_id)
        if not project:
            return {}

        resources = session.exec(
            select(Resource).where(Resource.project_id == project_id)
        ).all()

        resource_count = len(resources)
        if resource_count == 0:
            return {
                "id": project.id,
                "title": project.title,
                "status": project.status,
                "created_at": str(project.created_at)[:19],
                "updated_at": str(project.updated_at)[:19],
                "resource_count": 0,
                "avg_score": 0,
                "sources": {},
                "difficulties": {},
            }

        scores = [r.quality_score for r in resources if r.quality_score]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Count by source
        sources: dict[str, int] = {}
        for r in resources:
            src = r.source or "unknown"
            sources[src] = sources.get(src, 0) + 1

        # Count by difficulty
        difficulties: dict[str, int] = {}
        for r in resources:
            diff = r.difficulty or "unknown"
            difficulties[diff] = difficulties.get(diff, 0) + 1

        return {
            "id": project.id,
            "title": project.title,
            "status": project.status,
            "created_at": str(project.created_at)[:19],
            "updated_at": str(project.updated_at)[:19],
            "resource_count": resource_count,
            "avg_score": round(avg_score, 1),
            "sources": sources,
            "difficulties": difficulties,
        }


def list_projects_with_stats() -> list[dict]:
    """List all projects with aggregated stats."""
    projects = list_projects()
    result = []
    for p in projects:
        stats = get_project_stats(p.id)
        result.append(stats)
    return result
    return task


# select is already imported at the top
