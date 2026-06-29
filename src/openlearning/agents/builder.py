"""Builder Agent — learning system generation subgraph.

Generates a knowledge-graph-driven learning system with personalized paths.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState
from openlearning.log import get_logger

logger = get_logger("Builder")


async def builder_agent(state: AgentState) -> dict[str, Any]:
    """Builder subgraph: knowledge graph → enriched content → learning system.

    Reads: knowledge_graph, analyzed_resources, user_memory
    Writes: learning_system, status
    """
    graph = state.get("knowledge_graph", {})
    resources = state.get("analyzed_resources", [])
    memory = state.get("user_memory", {})
    user_request = state.get("user_request", "")

    # 1. Match resources to concepts
    knowledge_resources = _match_resources_to_concepts(graph, resources)

    # 2. Enrich concept nodes with LLM-generated content
    logger.info("输入知识图谱: %s 个节点", len(graph.get('nodes', [])))
    enriched_graph = await _enrich_concepts(graph, knowledge_resources, user_request)
    logger.info("丰富后图谱: %s 个节点", len(enriched_graph.get('nodes', [])))

    # 3. Generate personalized learning path
    learning_path = _generate_learning_path(enriched_graph, memory)

    # 4. Persist learning system to database
    await _persist_to_db(state, enriched_graph, learning_path, knowledge_resources)

    # 5. Save project for future memory
    await _save_project(state)

    # 6. Record learning events for concepts
    user_profile = state.get("user_profile", {})
    user_id = user_profile.get("user_id", "default")
    await _record_learning_events(user_id, enriched_graph)

    return {
        "learning_system": {
            "knowledge_graph": enriched_graph,
            "learning_path": learning_path,
            "knowledge_resources": knowledge_resources,
            "persisted": True,
        },
        "knowledge_graph": enriched_graph,
        "current_agent": "builder",
        "status": "done",
    }


def _flatten_str_list(items: list) -> list[str]:
    """Flatten a potentially nested list into a flat list of strings."""
    result = []
    for item in items:
        if isinstance(item, list):
            result.extend(str(i) for i in item if i)
        elif isinstance(item, str):
            result.append(item)
        else:
            result.append(str(item))
    return result


async def _enrich_concepts(
    graph: dict,
    knowledge_resources: dict[str, list[dict]],
    user_request: str = "",
) -> dict:
    """Enrich each concept node with LLM-generated content.

    For each concept: gather matched resource summaries → LLM generates
    a rich definition, explanation, key points, and examples.
    """
    import asyncio
    from openlearning.llm import achat_json

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    semaphore = asyncio.Semaphore(8)  # Limit concurrent LLM calls

    async def _enrich_one(node: dict) -> dict:
        async with semaphore:
            return await _enrich_node(node, knowledge_resources, user_request)

    enriched_nodes = await asyncio.gather(*[_enrich_one(n) for n in nodes])

    return {
        "nodes": list(enriched_nodes),
        "edges": edges,
        "topic": graph.get("topic", ""),
    }


async def _enrich_node(
    node: dict,
    knowledge_resources: dict[str, list[dict]],
    user_request: str,
) -> dict:
    """Enrich a single concept node with LLM content."""
    from openlearning.llm import achat_json

    concept_name = node.get("name", "")
    concept_type = node.get("type", "concept")
    concept_id = node.get("id", "")

    # Gather context from matched resources and save references
    matched = knowledge_resources.get(concept_id, [])
    resource_contexts = []
    references = []
    for r in matched[:5]:
        ctx = r.get("summary", "") or r.get("one_line_summary", "")
        if not ctx:
            ctx = r.get("snippet", "")
        if ctx:
            resource_contexts.append(f"- {r.get('title', '')}: {ctx[:300]}")
        if r.get("url"):
            references.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "source": r.get("source", ""),
                "quality_score": r.get("quality_score", 0),
            })

    # Save references to node
    node["references"] = references

    resources_text = "\n".join(resource_contexts) if resource_contexts else "无可用资源"

    existing_def = node.get("definition", "")
    if existing_def and existing_def.startswith("Subtopic:"):
        existing_def = ""

    from openlearning.agents.prompts import CONCEPT_ENRICH_PROMPT

    prompt = CONCEPT_ENRICH_PROMPT.format(
        concept_name=concept_name,
        user_request=user_request or "通用学习",
        concept_type=concept_type,
        resources_text=resources_text,
        existing_def=existing_def or "无",
    )

    try:
        result = await achat_json(
            messages=[{"role": "user", "content": prompt}],
            tier="standard",
            temperature=0.3,
        )
        node["definition"] = result.get("definition", node.get("definition", ""))
        node["explanation"] = result.get("explanation", "")
        node["key_points"] = _flatten_str_list(result.get("key_points", []))
        node["examples"] = _flatten_str_list(result.get("examples", []))
        node["common_mistakes"] = _flatten_str_list(result.get("common_mistakes", []))
        node["learning_tips"] = result.get("learning_tips", "")
        logger.info("✓ 丰富内容: %s", concept_name)
    except Exception as e:
        logger.error("✗ 内容生成失败: %s - %s", concept_name, e)
        # Keep existing data, ensure fields exist
        node.setdefault("explanation", "")
        node.setdefault("key_points", [])
        node.setdefault("examples", [])
        node.setdefault("common_mistakes", [])
        node.setdefault("learning_tips", "")

    return node


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
    """Match resources to knowledge graph concepts.

    策略：
    1. 精确匹配：概念关键词出现在资源标题/摘要中
    2. 主题兜底：所有资源的主题词匹配的概念也关联
    """
    nodes = graph.get("nodes", [])
    topic = graph.get("topic", "").lower()
    mapping: dict[str, list[dict]] = {}

    for node in nodes:
        node_id = node.get("id", "")
        node_name = node.get("name", "").lower()
        node_keywords = [kw for kw in node_name.replace("_", " ").split() if len(kw) > 2]

        matched = []
        for r in resources:
            title = r.get("title", "").lower()
            snippet = r.get("snippet", "") or r.get("summary", "") or ""
            snippet = snippet.lower()
            text = title + " " + snippet

            # 精确匹配：概念关键词
            if node_keywords and any(kw in text for kw in node_keywords):
                matched.append(r)
                continue

            # 主题兜底：概念名包含主题词 且 资源也包含主题词
            if topic and len(topic) > 2 and topic in node_name and topic in text:
                matched.append(r)

        # Sort by quality score, take top 5
        matched.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        mapping[node_id] = matched[:5]

    return mapping


async def _persist_to_db(
    state: dict,
    graph: dict,
    path: dict,
    resources: dict,
) -> None:
    """Persist learning system data to database."""
    try:
        from openlearning.database import (
            create_project,
            get_project,
            list_projects,
            save_learning_system,
        )

        # Find or create project
        user_request = state.get("user_request", "Untitled")
        project_id = state.get("project_id", "")

        # If project_id provided, verify it exists
        if project_id:
            project = get_project(project_id)
            if not project:
                project_id = ""  # Invalid ID, fall back to title search

        # Fall back to title search
        if not project_id:
            projects = list_projects()
            for p in projects:
                if p.title == user_request:
                    project_id = p.id
                    break

        # Create if still not found
        if not project_id:
            project = create_project(
                title=user_request,
                description=f"Auto-generated from: {user_request}",
            )
            project_id = project.id

        save_learning_system(
            project_id=project_id,
            knowledge_graph=graph,
            learning_path=path,
            knowledge_resources=resources,
        )
        logger.info("学习系统已持久化到数据库 (project: %s)", project_id)
    except Exception as e:
        logger.error("✗ 数据库持久化失败: %s", e)


async def _save_project(state: AgentState) -> None:
    """Save the project to database for future memory."""
    try:
        from openlearning.database import create_project, list_projects

        user_request = state.get("user_request", "Untitled")

        # Check if project with same title already exists
        existing = list_projects()
        for p in existing:
            if p.title == user_request:
                return  # Already exists, skip creation

        create_project(
            title=user_request,
            description=f"Auto-generated from: {user_request}",
        )
    except Exception:
        pass


async def _record_learning_events(user_id: str, graph: dict) -> None:
    """Record 'started' events for all concepts in the generated learning system."""
    try:
        from openlearning.tools.memory import record_event

        nodes = graph.get("nodes", [])
        for node in nodes[:20]:  # Limit to avoid too many events
            concept_id = node.get("id", "")
            if concept_id:
                try:
                    await record_event.ainvoke({
                        "user_id": user_id,
                        "concept_id": concept_id,
                        "event": "started",
                    })
                except Exception:
                    continue
        logger.info("记录学习事件: %s 个概念", min(len(nodes), 20))
    except Exception as e:
        logger.info("记录学习事件失败: %s", e)
