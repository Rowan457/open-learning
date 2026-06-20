"""Collector Agent — multi-source resource collection subgraph.

Collects resources from multiple sources in parallel, deduplicates, and persists.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from openlearning.agents.state import AgentState


async def collector_agent(state: AgentState) -> dict[str, Any]:
    """Collector subgraph: parallel multi-source collection → dedup → persist.

    首次采集：使用 Planner 生成的 search_queries
    后续采集：根据 Reflector 的 missing_concepts + missing_types 定向搜索

    Reads: search_queries, reflection, avoid_list
    Writes: raw_resources, collected_count, sources_queried
    """
    base_queries = state.get("search_queries", [])
    reflection = state.get("reflection", {})
    avoid_set = set(state.get("avoid_list", []))
    project_id = state.get("learning_plan", {}).get("project_id", "")

    # 根据 Reflector 决策生成定向查询
    queries = _build_queries(base_queries, reflection)

    if not queries:
        return {
            "raw_resources": [],
            "collected_count": 0,
            "sources_queried": [],
            "current_agent": "collector",
        }

    # 1. Parallel collection from multiple sources
    all_resources = await _parallel_collect(queries)

    # 2. Dedup by URL
    deduplicated = _deduplicate(all_resources, avoid_set)

    # 3. Add content hash for change detection
    for r in deduplicated:
        content = r.get("snippet", "") + r.get("title", "")
        r["content_hash"] = hashlib.md5(content.encode()).hexdigest()
        r["project_id"] = project_id

    # 4. Persist to database
    await _persist_resources(deduplicated)

    # 5. Track sources
    sources = list({r.get("source", "unknown") for r in deduplicated})

    prev_count = state.get("collected_count", 0)

    return {
        "raw_resources": deduplicated,
        "collected_count": prev_count + len(deduplicated),
        "sources_queried": sources,
        "current_agent": "collector",
    }


async def _parallel_collect(queries: list[str]) -> list[dict]:


def _build_queries(base_queries: list[str], reflection: dict) -> list[str]:
    """根据 Reflector 决策生成搜索词。

    - missing_concepts → 针对缺失概念生成精确搜索
    - missing_types → 针对缺失类型生成定向搜索
    - 无 reflection → 使用 Planner 的原始搜索词
    """
    if not reflection:
        return base_queries

    queries = list(base_queries)  # 保留原始查询

    # 缺什么资源 → 针对性搜索
    for concept in reflection.get("missing_concepts", [])[:5]:
        queries.append(f"{concept} tutorial")
        queries.append(f"{concept} 教程")

    # 需要什么类型 → 定向到对应数据源
    for rtype in reflection.get("missing_types", []):
        if rtype == "video":
            queries.append("video tutorial")
        elif rtype == "paper":
            queries.append("survey paper arxiv")
        elif rtype == "repo":
            queries.append("github examples")
        elif rtype == "article":
            queries.append("comprehensive guide blog")

    # 质量问题 → 提升搜索精度
    if reflection.get("quality_issue"):
        queries = [q + " official documentation" for q in queries[:3]] + queries

    # 时效性问题 → 加时间限定
    if reflection.get("freshness_issue"):
        queries = [q + " 2025 2026" for q in queries[:3]] + queries

    # 去重
    seen = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique



    """Collect resources from multiple sources in parallel."""
    from openlearning.skills.search import (
        arxiv_search,
        github_search,
        web_search,
        youtube_search,
    )

    tasks = []
    for query in queries[:10]:  # Limit to 10 queries to avoid rate limits
        query_lower = query.lower()

        if "arxiv" in query_lower or "paper" in query_lower:
            tasks.append(_safe_invoke(arxiv_search, {"query": query, "max_results": 10}))
        elif "video" in query_lower:
            tasks.append(_safe_invoke(youtube_search, {"query": query, "max_results": 10}))
        elif "github" in query_lower:
            tasks.append(_safe_invoke(github_search, {"query": query}))
        else:
            tasks.append(_safe_invoke(web_search, {"query": query, "max_results": 15}))
            tasks.append(_safe_invoke(arxiv_search, {"query": query, "max_results": 5}))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten results
    all_resources = []
    for result in results:
        if isinstance(result, list):
            all_resources.extend(result)
        elif isinstance(result, Exception):
            # Log but don't fail
            continue

    return all_resources


async def _safe_invoke(tool, input_data: dict) -> list[dict]:
    """Safely invoke a tool, returning empty list on error."""
    try:
        result = await tool.ainvoke(input_data)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def _deduplicate(resources: list[dict], avoid_set: set[str]) -> list[dict]:
    """Remove duplicates by URL and exclude already-seen URLs."""
    seen_urls: set[str] = set()
    deduplicated = []

    for r in resources:
        url = r.get("url", "")
        if not url:
            continue
        # Normalize URL
        url = url.rstrip("/").split("?")[0].split("#")[0]

        if url in seen_urls or url in avoid_set:
            continue

        seen_urls.add(url)
        r["url"] = url
        deduplicated.append(r)

    return deduplicated


async def _persist_resources(resources: list[dict]) -> None:
    """Save collected resources to database."""
    try:
        from openlearning.skills.persist import save_resource

        for r in resources[:50]:  # Limit batch size
            try:
                await save_resource.ainvoke({"resource": r})
            except Exception:
                continue
    except Exception:
        # Persistence failure shouldn't block the pipeline
        pass
