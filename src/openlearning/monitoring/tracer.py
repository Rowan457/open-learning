"""LangSmith tracing initialization and configuration."""

from __future__ import annotations

from typing import Any


def init_tracing() -> dict[str, Any]:
    """Initialize LangSmith tracing if configured.

    Returns {enabled, project}.
    """
    try:
        from openlearning.config import get_config

        config = get_config()

        if not config.langsmith.enabled:
            return {"enabled": False, "project": config.langsmith.project}

        if not config.langsmith.api_key:
            return {"enabled": False, "reason": "No API key configured"}

        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = config.langsmith.api_key
        os.environ["LANGCHAIN_PROJECT"] = config.langsmith.project

        return {
            "enabled": True,
            "project": config.langsmith.project,
        }

    except Exception as e:
        return {"enabled": False, "reason": str(e)}


def get_trace_url(run_id: str) -> str:
    """Get the LangSmith trace URL for a run."""
    try:
        from openlearning.config import get_config

        config = get_config()
        project = config.langsmith.project
        return f"https://smith.langchain.com/public/{project}/r/{run_id}"
    except Exception:
        return ""
