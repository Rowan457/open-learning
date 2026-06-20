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

    只负责执行 Planner 生成的 search_queries，不做路由决策。

    Reads: search_queries, avoid_list
    Writes: raw_resources, collected_count, sources_queried
    """
    queries = state.get("search_queries", [])
    avoid_set = set(state.get("avoid_list", []))
    project_id = state.get("learning_plan", {}).get("project_id", "")

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
