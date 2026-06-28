"""Collector Agent — multi-source resource collection subgraph.

Collects resources from multiple sources in parallel, deduplicates, and persists.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from openlearning.agents.state import AgentState
from openlearning.log import get_logger

logger = get_logger("Collector")


async def collector_agent(state: AgentState) -> dict[str, Any]:
    """Collector subgraph: parallel multi-source collection → dedup → persist.

    只负责执行 Planner 生成的 search_queries，不做路由决策。

    Reads: search_queries, avoid_list, incremental, since_days
    Writes: raw_resources, collected_count, sources_queried
    """
    queries = state.get("search_queries", [])
    project_id = state.get("project_id", "") or state.get("learning_plan", {}).get("project_id", "")
    incremental = state.get("incremental", False)
    since_days = state.get("since_days")

    # 增量模式: 用已有 URL 做去重, 计算 since_days
    avoid_set: set[str] = set()
    if incremental and project_id:
        from openlearning.database import get_existing_urls, get_last_crawl_date
        from datetime import datetime, timezone

        avoid_set = get_existing_urls(project_id)
        logger.info("增量模式: 已有 %s 条资源", len(avoid_set))

        # 自动计算 since_days (若未指定)
        if since_days is None:
            last_crawl = get_last_crawl_date(project_id)
            if last_crawl:
                delta = datetime.now(timezone.utc) - last_crawl.replace(tzinfo=timezone.utc)
                since_days = max(1, delta.days)
                logger.info("上次采集: %s, since_days=%s", last_crawl.date(), since_days)
            else:
                since_days = 30  # 首次增量, 默认查最近 30 天

    if not queries:
        return {
            "raw_resources": [],
            "collected_count": 0,
            "sources_queried": [],
            "current_agent": "collector",
        }

    # 1. Parallel collection from multiple sources
    all_resources, errors = await _parallel_collect(queries, since_days=since_days)

    # Debug: log collection stats
    logger.info("查询 %s 个，返回 %s 条资源", len(queries), len(all_resources))
    if errors:
        logger.warning("⚠ %s 个错误:", len(errors))
        for err in errors[:5]:
            print(f"  - {err}")

    # Debug: log per-source counts
    source_counts: dict[str, int] = {}
    for r in all_resources:
        src = r.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    if source_counts:
        logger.info("来源分布: %s", source_counts)
    if not all_resources:
        logger.info("查询词: %s", queries[:5])

    # 2. Dedup by URL
    deduplicated = _deduplicate(all_resources, avoid_set)

    # 3. Add content hash for change detection
    for r in deduplicated:
        content = r.get("snippet", "") + r.get("title", "")
        r["content_hash"] = hashlib.md5(content.encode()).hexdigest()
        r["project_id"] = project_id

    # 4. Persist to database
    await _persist_resources(deduplicated)

    # 4b. Record crawl tasks for update tracking
    if project_id and queries:
        try:
            from openlearning.database import record_crawl_task
            for query in queries[:10]:
                record_crawl_task(project_id, query, "multi", len(deduplicated))
        except Exception:
            pass

    # 5. Track sources
    sources = list({r.get("source", "unknown") for r in deduplicated})

    prev_count = state.get("collected_count", 0)

    # Log errors for debugging
    if errors:
        logger.warning("⚠ %s 个搜索任务失败:", len(errors))
        for err in errors[:5]:
            print(f"  - {err}")

    logger.info("返回 %s 条资源到状态", len(deduplicated))

    return {
        "raw_resources": deduplicated,
        "collected_count": prev_count + len(deduplicated),
        "sources_queried": sources,
        "search_errors": errors,
        "current_agent": "collector",
    }


def _is_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return any("一" <= c <= "鿿" for c in text)


async def _parallel_collect(
    queries: list[str], since_days: int | None = None
) -> tuple[list[dict], list[str]]:
    """Collect resources from multiple sources in parallel.

    策略：
    - 中文查询 → web + bilibili + zhihu（中文平台）
    - 英文查询 → web + arXiv + YouTube + GitHub
    Returns (resources, errors).
    """
    from openlearning.tools.search import (
        arxiv_search,
        bilibili_search,
        github_search,
        web_search,
        youtube_search,
        zhihu_search,
    )

    tasks = []
    task_labels = []
    extra: dict[str, Any] = {}
    if since_days is not None:
        extra["since_days"] = since_days

    # 分离中英文查询
    zh_queries = [q for q in queries if _is_chinese(q)][:3]
    en_queries = [q for q in queries if not _is_chinese(q)][:5]

    # 中文查询 → web + bilibili + zhihu
    for query in zh_queries:
        tasks.append(_safe_invoke(web_search, {"query": query, "max_results": 15, **extra}))
        task_labels.append(f"web: {query[:30]}")

        tasks.append(_safe_invoke(bilibili_search, {"query": query, "max_results": 15, **extra}))
        task_labels.append(f"bilibili: {query[:30]}")

        tasks.append(_safe_invoke(zhihu_search, {"query": query, "max_results": 10}))
        task_labels.append(f"zhihu: {query[:30]}")

    # 英文查询 → 所有 4 个源
    for query in en_queries:
        tasks.append(_safe_invoke(web_search, {"query": query, "max_results": 15, **extra}))
        task_labels.append(f"web: {query[:30]}")

        tasks.append(_safe_invoke(arxiv_search, {"query": query, "max_results": 10, **extra}))
        task_labels.append(f"arxiv: {query[:30]}")

        tasks.append(_safe_invoke(youtube_search, {"query": query, "max_results": 10, **extra}))
        task_labels.append(f"youtube: {query[:30]}")

        tasks.append(_safe_invoke(github_search, {"query": query, **extra}))
        task_labels.append(f"github: {query[:30]}")

    # 插件搜索（所有启用的自定义数据源）
    plugin_queries = (zh_queries + en_queries)[:3]  # 最多 3 个查询用插件
    for query in plugin_queries:
        tasks.append(_plugin_search(query, max_results=10))
        task_labels.append(f"plugin: {query[:30]}")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten results and collect errors
    all_resources = []
    errors = []
    for i, result in enumerate(results):
        label = task_labels[i] if i < len(task_labels) else f"task-{i}"
        if isinstance(result, list):
            all_resources.extend(result)
        elif isinstance(result, Exception):
            errors.append(f"[{label}] {type(result).__name__}: {result}")

    return all_resources, errors


async def _plugin_search(query: str, max_results: int = 10) -> list[dict]:
    """使用所有已启用插件搜索资源。"""
    try:
        from openlearning.plugins.manager import PluginManager
        pm = PluginManager()
        pm.discover()
        return await pm.search_all(query, max_results=max_results)
    except Exception:
        return []


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
    no_url_count = 0
    dup_count = 0
    avoid_count = 0

    for r in resources:
        url = r.get("url", "")
        if not url:
            no_url_count += 1
            continue
        # Normalize URL
        url = url.rstrip("/").split("?")[0].split("#")[0]

        if url in seen_urls:
            dup_count += 1
            continue
        if url in avoid_set:
            avoid_count += 1
            continue

        seen_urls.add(url)
        r["url"] = url
        deduplicated.append(r)

    if no_url_count or dup_count or avoid_count:
        logger.info("去重: %s → %s (无URL: %s, 重复: %s, 已推荐: %s)", len(resources), len(deduplicated), no_url_count, dup_count, avoid_count)

    return deduplicated


async def _persist_resources(resources: list[dict]) -> None:
    """Save collected resources to database."""
    try:
        from openlearning.tools.persist import save_resource

        for r in resources[:50]:  # Limit batch size
            try:
                await save_resource.ainvoke({"resource": r})
            except Exception:
                continue
    except Exception:
        # Persistence failure shouldn't block the pipeline
        pass
