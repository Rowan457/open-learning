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
    get_session,
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

    try:
        from openlearning.agents.graph import run_pipeline

        result = await run_pipeline(
            user_request=project.title,
            user_profile={"level": "beginner", "lang": ["zh", "en"], "user_id": "default"},
            max_iterations=2,
        )

        # Persist collected data to database
        kg = result.get("knowledge_graph", {})
        lp = result.get("learning_system", {}).get("learning_path", {})
        kr = result.get("learning_system", {}).get("knowledge_resources", {})

        if kg.get("nodes"):
            from openlearning.database import save_learning_system
            save_learning_system(project_id, kg, lp, kr)

        return {
            "status": "completed",
            "resources_collected": len(result.get("analyzed_resources", [])),
            "knowledge_graph_nodes": len(kg.get("nodes", [])),
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

    knowledge_graph = _load_knowledge_graph(project_id)
    learning_path = _load_learning_path(project_id)

    if not knowledge_graph.get("nodes"):
        raise HTTPException(status_code=404, detail="No knowledge graph data for this project. Run collect first.")

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


# ── Knowledge Graph API (for Vue frontend) ──────────────────


def _load_knowledge_graph(project_id: str) -> dict[str, Any]:
    """Load knowledge graph for a specific project."""
    from openlearning.database import get_learning_system

    ls = get_learning_system(project_id)
    if ls and ls.get("knowledge_graph", {}).get("nodes"):
        return ls["knowledge_graph"]

    return {"nodes": [], "edges": [], "topic": ""}


def _load_knowledge_resources(project_id: str) -> dict[str, Any]:
    """Load knowledge resources mapping for a specific project."""
    from openlearning.database import get_learning_system

    ls = get_learning_system(project_id)
    if ls and ls.get("knowledge_resources"):
        return ls["knowledge_resources"]

    return {}


def _load_learning_path(project_id: str) -> dict[str, Any]:
    """Load learning path for a specific project."""
    from openlearning.database import get_learning_system

    ls = get_learning_system(project_id)
    if ls and ls.get("learning_path", {}).get("steps"):
        return ls["learning_path"]

    return {"phases": [], "steps": []}


@api_router.get("/projects/{project_id}/graph")
async def get_knowledge_graph(project_id: str) -> dict[str, Any]:
    """Get knowledge graph (nodes + edges) for Vue frontend."""
    init_db()
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    graph = _load_knowledge_graph(project_id)
    return {
        "topic": project.title,
        "nodes": graph.get("nodes", []),
        "edges": graph.get("edges", []),
    }


@api_router.get("/projects/{project_id}/learning-path")
async def get_learning_path(project_id: str) -> dict[str, Any]:
    """Get learning path for Vue frontend."""
    init_db()
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    lp = _load_learning_path(project_id)
    graph = _load_knowledge_graph(project_id)

    # Enrich steps with node data
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    enriched_steps = []
    for step in lp.get("steps", []):
        node = nodes_by_id.get(step.get("concept", ""), {})
        enriched_steps.append({
            **step,
            "name": node.get("name", step.get("concept", "")),
            "difficulty": node.get("difficulty", ""),
            "importance": node.get("importance", 0.5),
        })

    return {
        "phases": lp.get("phases", []),
        "steps": enriched_steps,
        "total_steps": len(enriched_steps),
    }


@api_router.get("/projects/{project_id}/concepts")
async def list_concepts(project_id: str) -> list[dict[str, Any]]:
    """List all concepts for a project (for index page)."""
    init_db()
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    graph = _load_knowledge_graph(project_id)
    nodes = graph.get("nodes", [])
    return [
        {
            "id": n.get("id", ""),
            "name": n.get("name", ""),
            "type": n.get("type", "concept"),
            "difficulty": n.get("difficulty", "intermediate"),
            "importance": n.get("importance", 0.5),
            "definition": (n.get("definition", "") or "")[:200],
        }
        for n in nodes
    ]


@api_router.get("/projects/{project_id}/concepts/{concept_id}")
async def get_concept_detail(project_id: str, concept_id: str) -> dict[str, Any]:
    """Get concept detail with related edges and resources."""
    init_db()
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    graph = _load_knowledge_graph(project_id)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Find the concept node
    node = None
    for n in nodes:
        if n["id"] == concept_id:
            node = n
            break

    if not node:
        raise HTTPException(status_code=404, detail="Concept not found")

    # Find related edges
    related_edges = [e for e in edges if e.get("from") == concept_id or e.get("to") == concept_id]
    prereqs = [
        {"edge": e, "node": _find_node(nodes, e["from"])}
        for e in related_edges
        if e.get("type") == "prerequisite" and e.get("to") == concept_id
    ]
    extends = [
        {"edge": e, "node": _find_node(nodes, e["to"])}
        for e in related_edges
        if e.get("type") == "prerequisite" and e.get("from") == concept_id
    ]
    related = [
        {"edge": e, "node": _find_node(nodes, e["to"] if e.get("from") == concept_id else e["from"])}
        for e in related_edges
        if e.get("type") == "related"
    ]

    # Find resources
    all_resources = _load_knowledge_resources(project_id)
    resources = all_resources.get(concept_id, [])[:5]

    return {
        "node": node,
        "prerequisites": [
            {"id": p["node"]["id"], "name": p["node"]["name"], "reason": p["edge"].get("reason", ""), "weight": p["edge"].get("weight", 1.0)}
            for p in prereqs if p["node"]
        ],
        "extends": [
            {"id": e["node"]["id"], "name": e["node"]["name"], "reason": e["edge"].get("reason", ""), "weight": e["edge"].get("weight", 1.0)}
            for e in extends if e["node"]
        ],
        "related": [
            {"id": r["node"]["id"], "name": r["node"]["name"], "reason": r["edge"].get("reason", ""), "weight": r["edge"].get("weight", 1.0)}
            for r in related if r["node"]
        ],
        "resources": resources,
    }


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
    for n in nodes:
        if n["id"] == node_id:
            return n
    return None


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
