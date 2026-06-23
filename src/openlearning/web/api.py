"""REST API endpoints for the Web UI.

Endpoints:
- GET  /api/projects              → List projects
- POST /api/projects              → Create project
- GET  /api/projects/{id}         → Get project detail
- PUT  /api/projects/{id}         → Update project
- DELETE /api/projects/{id}       → Delete project
- GET  /api/projects/{id}/resources → List resources
- POST /api/projects/{id}/collect → Trigger collection
- GET  /api/projects/{id}/export  → Export project
- GET  /api/plugins               → List plugins
- PUT  /api/plugins/{name}/enable → Enable plugin
- PUT  /api/plugins/{name}/disable → Disable plugin
- POST /api/plugins/reload        → Reload plugins
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from openlearning.database import (
    create_project,
    delete_project,
    get_project,
    get_project_stats,
    get_resources_by_project,
    init_db,
    list_projects_with_stats,
    update_project,
)

api_router = APIRouter()


# ── Request/Response Models ─────────────────────────────────


class CreateProjectRequest(BaseModel):
    title: str
    description: str = ""


class UpdateProjectRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


# ── Project Endpoints ───────────────────────────────────────


@api_router.get("/projects")
async def list_projects() -> list[dict[str, Any]]:
    """List all projects with stats."""
    init_db()
    return list_projects_with_stats()


@api_router.post("/projects")
async def create_new_project(req: CreateProjectRequest) -> dict[str, Any]:
    """Create a new project."""
    init_db()
    project = create_project(req.title, req.description)
    stats = get_project_stats(project.id)
    return stats


@api_router.get("/projects/{project_id}")
async def get_project_detail(project_id: str) -> dict[str, Any]:
    """Get project detail with stats."""
    init_db()
    stats = get_project_stats(project_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Project not found")
    return stats


@api_router.put("/projects/{project_id}")
async def update_project_info(
    project_id: str, req: UpdateProjectRequest
) -> dict[str, Any]:
    """Update project title/description/status."""
    init_db()
    project = update_project(
        project_id,
        title=req.title,
        description=req.description,
        status=req.status,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return get_project_stats(project_id)


@api_router.delete("/projects/{project_id}")
async def delete_project_endpoint(project_id: str) -> dict[str, str]:
    """Delete a project and all its data."""
    init_db()
    if not delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted", "id": project_id}


# ── Resource Endpoints ──────────────────────────────────────


@api_router.get("/projects/{project_id}/resources")
async def list_resources(
    project_id: str,
    limit: int = Query(default=100, le=500),
) -> list[dict[str, Any]]:
    """List resources for a project."""
    init_db()
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    resources = get_resources_by_project(project_id)
    return [
        {
            "id": r.id,
            "title": r.title,
            "url": r.url,
            "source": r.source,
            "resource_type": r.resource_type,
            "quality_score": r.quality_score,
            "difficulty": r.difficulty,
            "language": r.language,
            "summary": r.summary,
            "fetched_at": str(r.fetched_at)[:19] if r.fetched_at else None,
        }
        for r in resources[:limit]
    ]


# ── Collection Endpoint ─────────────────────────────────────


@api_router.post("/projects/{project_id}/collect")
async def trigger_collection(project_id: str) -> dict[str, Any]:
    """Trigger resource collection for a project."""
    init_db()
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Run collection in background
    try:
        from openlearning.agents.graph import run_pipeline

        result = await run_pipeline(
            user_request=project.title,
            user_profile={"level": "beginner", "lang": ["zh", "en"], "user_id": "default"},
            max_iterations=2,
        )

        return {
            "status": "completed",
            "resources_collected": len(result.get("analyzed_resources", [])),
            "knowledge_graph_nodes": len(result.get("knowledge_graph", {}).get("nodes", [])),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


# ── Export Endpoint ─────────────────────────────────────────


@api_router.get("/projects/{project_id}/export")
async def export_project(
    project_id: str,
    format: str = Query(default="markdown", regex="^(markdown|anki|csv|json)$"),
) -> Any:
    """Export project data."""
    init_db()
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load knowledge graph
    from pathlib import Path
    import json

    kg_path = Path("output/data/knowledge-graph.json")
    lp_path = Path("output/data/learning-path.json")

    if not kg_path.exists():
        raise HTTPException(status_code=404, detail="Knowledge graph not found. Run collect first.")

    knowledge_graph = json.loads(kg_path.read_text(encoding="utf-8"))
    learning_path = json.loads(lp_path.read_text(encoding="utf-8")) if lp_path.exists() else {}

    if format == "markdown":
        from openlearning.exporters import export_markdown
        content = export_markdown(knowledge_graph, learning_path, project_title=project.title)
        return PlainTextResponse(content, media_type="text/plain")

    elif format == "anki":
        from openlearning.exporters import export_anki
        content = export_anki(knowledge_graph, deck_name=project.title)
        return PlainTextResponse(content, media_type="text/plain")

    elif format == "csv":
        from openlearning.exporters import export_csv
        content = export_csv(knowledge_graph)
        return PlainTextResponse(content, media_type="text/csv")

    elif format == "json":
        return knowledge_graph


# ── Plugin Endpoints ────────────────────────────────────────


@api_router.get("/plugins")
async def list_plugins() -> list[dict[str, Any]]:
    """List all plugins."""
    from openlearning.plugins.manager import PluginManager

    pm = PluginManager()
    return pm.list_plugins()


@api_router.put("/plugins/{name}/enable")
async def enable_plugin(name: str) -> dict[str, str]:
    """Enable a plugin."""
    from openlearning.plugins.manager import PluginManager

    pm = PluginManager()
    pm.discover()
    if not pm.enable(name):
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"status": "enabled", "name": name}


@api_router.put("/plugins/{name}/disable")
async def disable_plugin(name: str) -> dict[str, str]:
    """Disable a plugin."""
    from openlearning.plugins.manager import PluginManager

    pm = PluginManager()
    pm.discover()
    if not pm.disable(name):
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"status": "disabled", "name": name}


@api_router.post("/plugins/reload")
async def reload_plugins() -> dict[str, Any]:
    """Reload all plugins."""
    from openlearning.plugins.manager import PluginManager

    pm = PluginManager()
    discovered = pm.reload()
    return {"status": "reloaded", "count": len(discovered), "plugins": discovered}
