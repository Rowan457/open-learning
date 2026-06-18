"""Pytest configuration and fixtures."""

from __future__ import annotations

import pytest
from sqlmodel import SQLModel, create_engine, Session


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Create a test database session."""
    with Session(engine) as sess:
        yield sess


@pytest.fixture
def sample_graph():
    """Sample knowledge graph for testing."""
    return {
        "nodes": [
            {"id": "ownership", "name": "Ownership", "type": "concept", "difficulty": "intermediate", "importance": 0.9},
            {"id": "borrowing", "name": "Borrowing", "type": "concept", "difficulty": "intermediate", "importance": 0.8},
            {"id": "lifetimes", "name": "Lifetimes", "type": "concept", "difficulty": "advanced", "importance": 0.7},
        ],
        "edges": [
            {"from": "ownership", "to": "borrowing", "type": "prerequisite", "weight": 0.9},
            {"from": "borrowing", "to": "lifetimes", "type": "prerequisite", "weight": 0.8},
        ],
        "topic": "Rust",
    }


@pytest.fixture
def sample_resources():
    """Sample resources for testing."""
    return [
        {
            "url": "https://example.com/rust-ownership",
            "title": "Understanding Rust Ownership",
            "source": "google",
            "resource_type": "article",
            "quality_score": 8.5,
            "snippet": "A comprehensive guide to Rust ownership model.",
        },
        {
            "url": "https://arxiv.org/abs/12345",
            "title": "Memory Safety in Rust",
            "source": "arxiv",
            "resource_type": "paper",
            "quality_score": 9.0,
            "snippet": "Academic paper on Rust memory safety.",
        },
        {
            "url": "https://youtube.com/watch?v=abc",
            "title": "Rust Tutorial for Beginners",
            "source": "youtube",
            "resource_type": "video",
            "quality_score": 7.0,
            "snippet": "Video tutorial on Rust basics.",
        },
    ]
