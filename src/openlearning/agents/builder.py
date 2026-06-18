"""Builder Agent — learning system generation subgraph.

Generates a knowledge-graph-driven learning system with personalized paths.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


async def builder_agent(state: AgentState) -> dict[str, Any]:
    """Builder subgraph: knowledge graph → learning path → learning system.

    Reads: knowledge_graph, analyzed_resources, user_memory
    Writes: learning_system, status
    """
    graph = state.get("knowledge_graph", {})
    resources = state.get("analyzed_resources", [])
    memory = state.get("user_memory", {})

    # 1. Generate personalized learning path
    learning_path = _generate_learning_path(graph, memory)

    # 2. Match resources to concepts
    knowledge_resources = _match_resources_to_concepts(graph, resources)

    # 3. Build the learning system site
    site_result = await _build_site(graph, learning_path, knowledge_resources)

    # 4. Save project for future memory
    await _save_project(state)

    return {
        "learning_system": {
            "site_path": site_result.get("site_path", ""),
            "knowledge_graph": graph,
            "learning_path": learning_path,
            "knowledge_resources": knowledge_resources,
            "pages_generated": site_result.get("pages_generated", 0),
        },
        "current_agent": "builder",
        "status": "done",
    }


def _generate_learning_path(graph: dict, memory: dict) -> dict:
    """Generate a personalized learning path from the knowledge graph."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    mastery = memory.get("mastery", {})

    # Get mastery sets
    mastered_ids = {m.get("concept_id", "") for m in mastery.get("mastered", [])}
    learning_ids = {m.get("concept_id", "") for m in mastery.get("learning", [])}

    # Topological sort based on prerequisite edges
    topo_order = _topological_sort(nodes, edges)

    steps = []
    for concept_id in topo_order:
        if concept_id in mastered_ids:
            continue  # Skip mastered concepts
        elif concept_id in learning_ids:
            steps.append({
                "concept": concept_id,
                "action": "continue",
                "priority": "high",
            })
        else:
            steps.append({
                "concept": concept_id,
                "action": "learn",
                "priority": "normal",
            })

    # Insert review steps for due concepts
    due_reviews = mastery.get("due_reviews", [])
    for review in due_reviews[:3]:
        concept_id = review.get("concept_id", "")
        if concept_id not in [s["concept"] for s in steps]:
            steps.insert(0, {
                "concept": concept_id,
                "action": "review",
                "priority": "high",
            })

    return {
        "steps": steps,
        "total_steps": len(steps),
        "skipped": len(mastered_ids),
    }


def _topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Topological sort of knowledge graph nodes based on prerequisite edges."""
    # Build adjacency list (prerequisite edges only)
    node_ids = {n.get("id", "") for n in nodes}
    in_degree = {nid: 0 for nid in node_ids}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for edge in edges:
        if edge.get("type") == "prerequisite":
            src = edge.get("from", "")
            dst = edge.get("to", "")
            if src in node_ids and dst in node_ids:
                adj[src].append(dst)
                in_degree[dst] = in_degree.get(dst, 0) + 1

    # Kahn's algorithm
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    result = []

    while queue:
        # Sort by importance (descending) for deterministic ordering
        queue.sort(key=lambda nid: _get_node_importance(nodes, nid), reverse=True)
        node = queue.pop(0)
        result.append(node)

        for neighbor in adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Add any nodes not in result (isolated nodes)
    for nid in node_ids:
        if nid not in result:
            result.append(nid)

    return result


def _get_node_importance(nodes: list[dict], node_id: str) -> float:
    """Get importance score for a node."""
    for n in nodes:
        if n.get("id") == node_id:
            return n.get("importance", 0.5)
    return 0.5


def _match_resources_to_concepts(graph: dict, resources: list[dict]) -> dict[str, list[dict]]:
    """Match resources to knowledge graph concepts."""
    nodes = graph.get("nodes", [])
    mapping: dict[str, list[dict]] = {}

    for node in nodes:
        node_id = node.get("id", "")
        node_name = node.get("name", "").lower()
        node_keywords = node_name.replace("_", " ").split()

        matched = []
        for r in resources:
            title = r.get("title", "").lower()
            snippet = r.get("snippet", "").lower()
            text = title + " " + snippet

            # Check if any keyword appears in the resource
            if any(kw in text for kw in node_keywords if len(kw) > 2):
                matched.append(r)

        # Sort by quality score, take top 5
        matched.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        mapping[node_id] = matched[:5]

    return mapping


async def _build_site(graph: dict, path: dict, resources: dict) -> dict:
    """Build the learning system site."""
    try:
        from openlearning.skills.render import build_learning_system

        return await build_learning_system.ainvoke({
            "knowledge_graph": graph,
            "learning_path": path,
            "knowledge_resources": resources,
            "output_dir": "./output/",
        })
    except Exception as e:
        return {"error": str(e), "site_path": "", "pages_generated": 0}


async def _save_project(state: AgentState) -> None:
    """Save the project to database for future memory."""
    try:
        from openlearning.database import create_project

        create_project(
            title=state.get("user_request", "Untitled"),
            description=f"Auto-generated from: {state.get('user_request', '')}",
        )
    except Exception:
        pass
