"""Planner Agent — learning plan generation subgraph.

Analyzes user request, generates knowledge tree and search queries.
"""

from __future__ import annotations

import re
from typing import Any

from openlearning.agents.state import AgentState


async def planner_agent(state: AgentState) -> dict[str, Any]:
    """Planner subgraph: analyze request → expand knowledge tree → generate search queries.

    Reads: user_request, user_profile, user_memory
    Writes: knowledge_graph, search_queries, learning_plan
    """
    user_request = state.get("user_request", "")
    user_profile = state.get("user_profile", {})
    user_memory = state.get("user_memory", {})

    # 1. Analyze user request
    analysis = _analyze_request(user_request, user_profile)

    # 2. Expand knowledge tree
    knowledge_graph = _expand_knowledge_graph(analysis)

    # 3. Generate search queries
    search_queries = _generate_search_queries(knowledge_graph, analysis, user_profile)

    # 4. Build crawl plan
    crawl_plan = _build_crawl_plan(search_queries, analysis)

    return {
        "knowledge_graph": knowledge_graph,
        "search_queries": search_queries,
        "learning_plan": {
            "analysis": analysis,
            "tree": knowledge_graph,
            "crawl_plan": crawl_plan,
        },
        "current_agent": "planner",
    }


def _analyze_request(request: str, profile: dict) -> dict:
    """Analyze user's learning request."""
    # Extract topic keywords
    # Remove common prefixes
    cleaned = re.sub(
        r"^(我想学|我想学习|学习|learn|study|about|了解)\s*",
        "",
        request.strip(),
        flags=re.IGNORECASE,
    )

    topic = cleaned.strip()
    level = profile.get("level", "beginner")
    languages = profile.get("lang", ["zh", "en"])

    # Determine subtopics based on topic
    subtopics = _infer_subtopics(topic)

    # Determine resource types based on preferences
    resource_types = profile.get("resource_types", ["article", "video", "paper", "repo"])

    return {
        "topic": topic,
        "subtopics": subtopics,
        "level": level,
        "languages": languages,
        "resource_types": resource_types,
    }


def _infer_subtopics(topic: str) -> list[str]:
    """Infer subtopics from a topic string."""
    topic_lower = topic.lower()

    # Common topic → subtopics mapping
    topic_map = {
        "rust": ["ownership", "borrowing", "lifetimes", "traits", "error handling", "async", "macros", "cargo"],
        "python": ["data types", "functions", "classes", "decorators", "async", "testing", "packaging"],
        "machine learning": ["supervised learning", "unsupervised learning", "neural networks", "evaluation", "feature engineering"],
        "deep learning": ["neural networks", "CNN", "RNN", "transformer", "training", "optimization"],
        "transformer": ["attention mechanism", "self-attention", "positional encoding", "encoder-decoder", "fine-tuning"],
        "web development": ["HTML", "CSS", "JavaScript", "frameworks", "APIs", "deployment"],
        "system design": ["scalability", "caching", "databases", "load balancing", "microservices"],
        "quantum computing": ["qubits", "quantum gates", "entanglement", "quantum algorithms", "error correction"],
    }

    # Check for matches
    for key, subs in topic_map.items():
        if key in topic_lower:
            return subs

    # Default: generate generic subtopics
    return [
        f"{topic} basics",
        f"{topic} fundamentals",
        f"{topic} advanced concepts",
        f"{topic} best practices",
        f"{topic} examples",
    ]


def _expand_knowledge_graph(analysis: dict) -> dict:
    """Build a knowledge graph from the analysis."""
    topic = analysis["topic"]
    subtopics = analysis["subtopics"]

    nodes = []
    edges = []

    # Root node
    root_id = topic.lower().replace(" ", "_")
    nodes.append({
        "id": root_id,
        "name": topic,
        "type": "concept",
        "definition": f"Core concepts of {topic}",
        "difficulty": analysis.get("level", "intermediate"),
        "importance": 1.0,
    })

    # Subtopic nodes
    for i, sub in enumerate(subtopics):
        sub_id = f"{root_id}_{sub.lower().replace(' ', '_')}"
        nodes.append({
            "id": sub_id,
            "name": sub,
            "type": "concept",
            "definition": f"Subtopic: {sub}",
            "difficulty": "intermediate",
            "importance": 0.8 - i * 0.05,
        })

        # Edge: topic → subtopic (prerequisite)
        edges.append({
            "from": root_id,
            "to": sub_id,
            "type": "prerequisite",
            "weight": 0.9,
            "reason": f"{sub} is a core aspect of {topic}",
        })

    # Add some related edges between subtopics
    for i in range(len(subtopics) - 1):
        sub1_id = f"{root_id}_{subtopics[i].lower().replace(' ', '_')}"
        sub2_id = f"{root_id}_{subtopics[i + 1].lower().replace(' ', '_')}"
        edges.append({
            "from": sub1_id,
            "to": sub2_id,
            "type": "related",
            "weight": 0.5,
            "reason": "Sequential subtopics",
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "topic": topic,
    }


def _generate_search_queries(graph: dict, analysis: dict, profile: dict) -> list[str]:
    """Generate search query matrix."""
    topic = analysis["topic"]
    languages = analysis.get("languages", ["zh", "en"])
    queries = []

    # Main topic queries
    for lang in languages:
        if lang == "zh":
            queries.append(f"{topic} 教程 入门")
            queries.append(f"{topic} 学习资源 推荐")
        else:
            queries.append(f"{topic} tutorial beginner")
            queries.append(f"{topic} best resources")

    # Subtopic queries
    for node in graph.get("nodes", []):
        name = node.get("name", "")
        if name == topic:
            continue
        for lang in languages[:1]:  # Limit to primary language for subtopics
            if lang == "zh":
                queries.append(f"{name} 教程")
            else:
                queries.append(f"{name} tutorial")

    # Academic queries
    queries.append(f"{topic} survey paper")
    queries.append(f"arxiv {topic}")

    # Video queries
    queries.append(f"{topic} video tutorial")

    # Code queries
    queries.append(f"{topic} github examples")

    return queries


def _build_crawl_plan(queries: list[str], analysis: dict) -> list[dict]:
    """Build a structured crawl plan from queries."""
    plan = []

    for i, query in enumerate(queries):
        # Determine source based on query content
        sources = ["web"]
        if "arxiv" in query.lower() or "paper" in query.lower():
            sources = ["arxiv"]
        elif "video" in query.lower():
            sources = ["youtube"]
        elif "github" in query.lower():
            sources = ["github"]

        plan.append({
            "query": query,
            "sources": sources,
            "priority": max(1, 10 - i),  # Higher priority for earlier queries
            "max_results": 15 if i < 4 else 10,
        })

    return plan
