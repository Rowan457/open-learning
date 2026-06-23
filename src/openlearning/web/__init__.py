"""Web UI — FastAPI-based management panel.

Provides REST API and HTML interface for managing projects,
viewing resources, triggering collections, and more.
"""

from openlearning.web.app import create_app

__all__ = ["create_app"]
