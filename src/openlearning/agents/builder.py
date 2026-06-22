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

    # 4. Build the learning system site
    site_result = await _build_site(enriched_graph, learning_path, knowledge_resources)

    # 4. Save project for future memory
    await _save_project(state)

    # 5. Record learning events for concepts
    user_profile = state.get("user_profile", {})
    user_id = user_profile.get("user_id", "default")
    await _record_learning_events(user_id, enriched_graph)

    return {
        "learning_system": {
            "site_path": site_result.get("site_path", ""),
            "knowledge_graph": enriched_graph,
            "learning_path": learning_path,
            "knowledge_resources": knowledge_resources,
            "pages_generated": site_result.get("pages_generated", 0),
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

    # Gather context from matched resources
    matched = knowledge_resources.get(concept_id, [])
    resource_contexts = []
    for r in matched[:3]:
        ctx = r.get("summary", "") or r.get("one_line_summary", "")
        if not ctx:
            ctx = r.get("snippet", "")
        if ctx:
            resource_contexts.append(f"- {r.get('title', '')}: {ctx[:300]}")

    resources_text = "\n".join(resource_contexts) if resource_contexts else "无可用资源"

    existing_def = node.get("definition", "")
    if existing_def and existing_def.startswith("Subtopic:"):
        existing_def = ""

    prompt = f"""你是一位专业的知识整理助手。请为知识点 "{concept_name}" 生成丰富、有教育价值的内容。

学习主题背景：{user_request or "通用学习"}
概念类型：{concept_type}

相关资源摘要：
{resources_text}

已有定义：{existing_def or "无"}

请以 JSON 格式输出：
{{
  "definition": "清晰准确的概念定义（2-4句话，要有实质内容）",
  "explanation": "深入浅出的解释（3-5段，帮助理解这个概念为什么重要、如何工作）",
  "key_points": ["要点1", "要点2", "要点3", "要点4", "要点5"],
  "examples": ["实际应用示例1", "实际应用示例2"],
  "common_mistakes": ["常见误解1", "常见误解2"],
  "learning_tips": "学习建议（1-2句话）"
}}

要求：
- 内容要有实质价值，不要空泛的描述
- 用中文回答
- explanation 要有层次感，从简到难
- examples 要具体、可操作"""

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

        result = await build_learning_system.ainvoke({
            "knowledge_graph": graph,
            "learning_path": path,
            "knowledge_resources": resources,
            "output_dir": "./output/",
        })
        logger.info("站点生成: %s 页", result.get('pages_generated', 0))
        return result
    except Exception as e:
        import traceback
        logger.error("✗ 站点生成失败: %s", e)
        traceback.print_exc()
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


async def _record_learning_events(user_id: str, graph: dict) -> None:
    """Record 'started' events for all concepts in the generated learning system."""
    try:
        from openlearning.skills.memory import record_event

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
