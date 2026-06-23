"""SQLModel data models for OpenLearning.

All models map to SQLite tables defined in PROJECT_SPECS.md §7.1.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


# ── Project ──────────────────────────────────────────────────

class Project(SQLModel, table=True):
    """Learning project."""

    __tablename__ = "projects"

    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str
    description: Optional[str] = None
    status: str = Field(default="active")  # active / paused / archived
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    topics: List["Topic"] = Relationship(back_populates="project")
    resources: List["Resource"] = Relationship(back_populates="project")
    crawl_tasks: List["CrawlTask"] = Relationship(back_populates="project")


# ── Topic ────────────────────────────────────────────────────

class Topic(SQLModel, table=True):
    """Topic node in the knowledge tree."""

    __tablename__ = "topics"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    parent_id: Optional[str] = Field(default=None, foreign_key="topics.id")
    title: str
    description: Optional[str] = None
    sort_order: int = Field(default=0)

    # Relationships
    project: Project = Relationship(back_populates="topics")
    resource_topics: List["ResourceTopic"] = Relationship(back_populates="topic")


# ── Resource ─────────────────────────────────────────────────

class Resource(SQLModel, table=True):
    """Learning resource (article, video, paper, repo, course)."""

    __tablename__ = "resources"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    url: str = Field(unique=True)
    title: str
    source: str  # google / arxiv / youtube / github / ...
    resource_type: str  # article / video / paper / repo / course
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    content_hash: Optional[str] = None
    summary: Optional[str] = None
    key_points: Optional[str] = None  # JSON array
    quality_score: float = Field(default=0.0)
    difficulty: Optional[str] = None  # beginner / intermediate / advanced
    reading_time: Optional[int] = None  # minutes
    language: str = Field(default="en")
    metadata_json: Optional[str] = Field(default=None, alias="metadata")

    # Relationships
    project: Project = Relationship(back_populates="resources")
    resource_topics: List["ResourceTopic"] = Relationship(back_populates="resource")
    quality_scores: List["QualityScore"] = Relationship(back_populates="resource")
    updates: List["Update"] = Relationship(back_populates="resource")


class ResourceTopic(SQLModel, table=True):
    """Many-to-many: resource ↔ topic."""

    __tablename__ = "resource_topics"

    resource_id: str = Field(foreign_key="resources.id", primary_key=True)
    topic_id: str = Field(foreign_key="topics.id", primary_key=True)
    relevance: float = Field(default=1.0)

    resource: Resource = Relationship(back_populates="resource_topics")
    topic: Topic = Relationship(back_populates="resource_topics")


# ── Quality Score ─────────────────────────────────────────────

class QualityScore(SQLModel, table=True):
    """Per-dimension quality score for a resource."""

    __tablename__ = "quality_scores"

    id: str = Field(default_factory=_uuid, primary_key=True)
    resource_id: str = Field(foreign_key="resources.id")
    dimension: str  # content / teaching / freshness / authority / readability
    score: float
    reasoning: Optional[str] = None

    resource: Resource = Relationship(back_populates="quality_scores")


# ── Crawl Task ───────────────────────────────────────────────

class CrawlTask(SQLModel, table=True):
    """Crawl task in the task queue."""

    __tablename__ = "crawl_tasks"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    query: str
    source: str
    status: str = Field(default="pending")  # pending / running / done / failed
    priority: int = Field(default=5)
    result_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    project: Project = Relationship(back_populates="crawl_tasks")


# ── Update Tracking ──────────────────────────────────────────

class Update(SQLModel, table=True):
    """Resource change detection record."""

    __tablename__ = "updates"

    id: str = Field(default_factory=_uuid, primary_key=True)
    resource_id: str = Field(foreign_key="resources.id")
    change_type: str  # new / updated / removed
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    resource: Resource = Relationship(back_populates="updates")


# ── Knowledge Graph Entities ─────────────────────────────────

class Concept(SQLModel, table=True):
    """Knowledge concept extracted by Analyzer."""

    __tablename__ = "concepts"

    id: str = Field(primary_key=True)  # e.g. "rust_ownership"
    name: str
    domain: Optional[str] = None  # e.g. "rust", "machine-learning"
    type: str  # concept / principle / technology / practice
    definition: Optional[str] = None
    difficulty: Optional[str] = None  # beginner / intermediate / advanced
    importance: float = Field(default=0.5)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    relations_from: List["ConceptRelation"] = Relationship(
        back_populates="from_concept",
        sa_relationship_kwargs={"foreign_keys": "[ConceptRelation.from_id]"},
    )
    relations_to: List["ConceptRelation"] = Relationship(
        back_populates="to_concept",
        sa_relationship_kwargs={"foreign_keys": "[ConceptRelation.to_id]"},
    )


class ConceptRelation(SQLModel, table=True):
    """Directed edge between two concepts."""

    __tablename__ = "concept_relations"

    id: str = Field(default_factory=_uuid, primary_key=True)
    from_id: str = Field(foreign_key="concepts.id")
    to_id: str = Field(foreign_key="concepts.id")
    type: str  # prerequisite / extends / related
    weight: float = Field(default=1.0)
    reason: Optional[str] = None

    from_concept: Concept = Relationship(
        back_populates="relations_from",
        sa_relationship_kwargs={"foreign_keys": "[ConceptRelation.from_id]"},
    )
    to_concept: Concept = Relationship(
        back_populates="relations_to",
        sa_relationship_kwargs={"foreign_keys": "[ConceptRelation.to_id]"},
    )


# ── Learning Memory ──────────────────────────────────────────

class ConceptMastery(SQLModel, table=True):
    """Per-user concept mastery (Learning Memory core table)."""

    __tablename__ = "concept_mastery"

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str
    concept_id: str = Field(foreign_key="concepts.id")
    mastery: float = Field(default=0.0)  # 0.0 – 1.0
    stability: float = Field(default=1.0)
    review_count: int = Field(default=0)
    last_practiced: Optional[datetime] = None
    next_review: Optional[datetime] = None
    learned_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LearningEvent(SQLModel, table=True):
    """Learning trajectory event for a concept."""

    __tablename__ = "learning_events"

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str
    concept_id: str = Field(foreign_key="concepts.id")
    event_type: str  # started / practiced / mastered / reviewed / tested
    resource_id: Optional[str] = Field(default=None, foreign_key="resources.id")
    score: Optional[float] = None
    time_spent: Optional[int] = None  # seconds
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResourceInteraction(SQLModel, table=True):
    """User interaction with a resource."""

    __tablename__ = "resource_interactions"

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str
    resource_id: str = Field(foreign_key="resources.id")
    action: str  # viewed / completed / bookmarked / rated / skipped
    rating: Optional[float] = None  # 1-5
    time_spent: Optional[int] = None  # seconds
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Learning System (persisted builder output) ────────────────

class LearningSystem(SQLModel, table=True):
    """Persisted learning system data (knowledge graph + learning path + resources)."""

    __tablename__ = "learning_systems"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", unique=True)
    knowledge_graph_json: Optional[str] = None  # JSON: {nodes, edges, topic}
    learning_path_json: Optional[str] = None     # JSON: {steps, phases}
    resources_json: Optional[str] = None         # JSON: {concept_id: [resources]}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
