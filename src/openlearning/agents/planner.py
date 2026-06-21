"""Planner Agent — learning plan generation subgraph.

Analyzes user request, generates knowledge tree and search queries.
"""

from __future__ import annotations

import re
from typing import Any

from openlearning.agents.state import AgentState


async def planner_agent(state: AgentState) -> dict[str, Any]:
    """Planner subgraph: analyze request → expand knowledge tree → generate search queries.

    首次调用：完整规划
    被 Reflector 调回：根据 missing_concepts + missing_types 调整搜索计划

    Reads: user_request, user_profile, user_memory, reflection
    Writes: knowledge_graph, search_queries, learning_plan
    """
    user_request = state.get("user_request", "")
    user_profile = state.get("user_profile", {})
    user_memory = state.get("user_memory", {})
    reflection = state.get("reflection", {})
    existing_graph = state.get("knowledge_graph", {})

    # 1. Analyze user request
    analysis = _analyze_request(user_request, user_profile)

    # 2. Expand knowledge tree (复用已有图谱，避免重复构建)
    if existing_graph and existing_graph.get("nodes"):
        knowledge_graph = existing_graph
    else:
        knowledge_graph = _expand_knowledge_graph(analysis)

    # 3. Generate search queries
    if reflection and reflection.get("should_continue"):
        # Reflector 驱动的重新规划：针对性搜索
        search_queries = _replan_from_reflection(reflection, analysis)
    else:
        # 首次规划
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


def _replan_from_reflection(reflection: dict, analysis: dict) -> list[str]:
    """根据 Reflector 的反馈重新生成搜索词。

    Reflector 输出:
    - missing_concepts: 缺什么资源
    - missing_types: 需要什么类型
    """
    queries = []
    topic = analysis.get("topic", "")

    # 缺什么资源 → 针对性搜索
    for concept in reflection.get("missing_concepts", [])[:5]:
        queries.append(f"{concept} tutorial")
        queries.append(f"{concept} 教程")

    # 需要什么类型 → 定向数据源
    for rtype in reflection.get("missing_types", []):
        if rtype == "video":
            queries.append(f"{topic} video tutorial youtube")
        elif rtype == "paper":
            queries.append(f"{topic} survey paper arxiv")
        elif rtype == "repo":
            queries.append(f"{topic} github examples")
        elif rtype == "article":
            queries.append(f"{topic} comprehensive guide blog")

    # 质量问题 → 提升搜索精度
    if reflection.get("quality_issue"):
        queries.append(f"{topic} official documentation")
        queries.append(f"{topic} best practices权威教程")

    # 时效性问题 → 加时间限定
    if reflection.get("freshness_issue"):
        queries.append(f"{topic} 2025 2026 latest")

    return queries


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
    """Generate search query matrix.

    为不同数据源生成不同查询：
    - 中文查询 → web search (SerpAPI/Tavily)
    - 英文查询 → arXiv/YouTube/GitHub
    """
    topic = analysis["topic"]
    subtopics = analysis.get("subtopics", [])
    languages = analysis.get("languages", ["zh", "en"])
    queries = []

    # 提取英文关键词（用于国际源）
    en_keywords = _extract_english_keywords(topic, subtopics)

    # ── Web search 查询（中英文均可）─────────────────────
    for lang in languages:
        if lang == "zh":
            queries.append(f"{topic} 教程 入门")
            queries.append(f"{topic} 学习资源 推荐")
        else:
            queries.append(f"{en_keywords} tutorial beginner")
            queries.append(f"{en_keywords} best resources")

    # ── arXiv 查询（必须英文）───────────────────────────
    queries.append(f"{en_keywords} survey")
    queries.append(f"{en_keywords} tutorial")

    # ── YouTube 查询（英文优先）────────────────────────
    queries.append(f"{en_keywords} tutorial video")
    queries.append(f"{en_keywords} course")

    # ── GitHub 查询（英文）─────────────────────────────
    queries.append(f"{en_keywords} examples")
    queries.append(f"{en_keywords} awesome")

    # ── 子主题查询 ─────────────────────────────────────
    for sub in subtopics[:3]:
        en_sub = _extract_english_keywords(sub, [])
        if en_sub:
            queries.append(f"{en_sub} tutorial")

    return queries


def _extract_english_keywords(topic: str, subtopics: list[str]) -> str:
    """从主题中提取英文关键词。

    如果主题包含中文，尝试提取其中的英文部分。
    如果全是中文，返回主题本身（让搜索 API 自行处理）。
    """
    import re

    # 提取主题中的英文单词
    en_words = re.findall(r"[a-zA-Z]+", topic)
    if en_words:
        return " ".join(en_words)

    # 也从子主题中提取
    for sub in subtopics:
        en_words = re.findall(r"[a-zA-Z]+", sub)
        if en_words:
            return " ".join(en_words[:3])

    # 全是中文，返回原主题
    return topic


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
