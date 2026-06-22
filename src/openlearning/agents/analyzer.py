"""Analyzer Agent — content analysis and knowledge extraction subgraph.

Two-stage analysis: rule-based pre-filter → LLM deep analysis for high-score resources.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


async def analyzer_agent(state: AgentState) -> dict[str, Any]:
    """Analyzer subgraph: three-stage analysis pipeline.

    Stage 1: Rule-based scoring (zero LLM cost)
    Stage 2: Fetch full content for top resources
    Stage 3: LLM deep analysis (knowledge extraction, summary, tagging)

    Reads: raw_resources, knowledge_graph, avoid_list
    Writes: analyzed_resources, extracted_concepts, concept_relations, knowledge_graph
    """
    resources = state.get("raw_resources", [])
    knowledge_graph = state.get("knowledge_graph", {})
    avoid_list = set(state.get("avoid_list", []))

    print(f"[Analyzer] 收到 {len(resources)} 条资源")

    if not resources:
        print("[Analyzer] 无资源，跳过分析")
        return {
            "analyzed_resources": [],
            "extracted_concepts": [],
            "concept_relations": [],
            "knowledge_graph": knowledge_graph,
            "avg_quality_score": 0.0,
            "current_agent": "analyzer",
        }

    # ── Stage 1: Rule-based pre-filter (zero LLM cost) ──────
    scored_resources = await _rule_based_scoring(resources)

    # Split by quality threshold
    high_score = [r for r in scored_resources if r.get("quality_score", 0) >= 6.0]
    low_score = [r for r in scored_resources if r.get("quality_score", 0) < 6.0]

    # Mark low-score as metadata-only
    for r in low_score:
        r["analysis_level"] = "metadata_only"

    # ── Stage 2: Fetch full content for top high-score resources ──
    # Sort by quality, fetch top 8 to balance depth vs cost
    high_score.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    fetch_targets = high_score[:8]
    fetch_rest = high_score[8:]

    print(f"[Analyzer] 抓取 {len(fetch_targets)} 条资源全文...")
    fetched = await _fetch_contents(fetch_targets)

    # Merge fetched content back
    for r in fetch_rest:
        r["full_content"] = r.get("snippet", "")
    for r in fetched:
        if not r.get("full_content"):
            r["full_content"] = r.get("snippet", "")

    all_high = fetched + fetch_rest

    # ── Stage 3: LLM deep analysis (parallel) ──────────────
    import asyncio
    semaphore = asyncio.Semaphore(8)  # Max 8 concurrent LLM calls
    all_concepts = []
    all_relations = []

    async def _analyze_one(resource: dict) -> dict:
        """Analyze a single resource: extract + tag + summarize in parallel."""
        async with semaphore:
            content = resource.get("full_content", "") or resource.get("snippet", "")
            if len(content) < 50:
                content = resource.get("snippet", "") + " " + resource.get("title", "")

            # Run extract, tag, summarize concurrently
            extract_task = _llm_extract(content)
            tag_task = _llm_tag(content, resource.get("title", ""))
            summary_task = _llm_summarize(content)

            results = await asyncio.gather(extract_task, tag_task, summary_task, return_exceptions=True)

            # Extract
            concepts = []
            if isinstance(results[0], dict):
                concepts = results[0].get("concepts", [])
            elif isinstance(results[0], Exception):
                try:
                    from openlearning.skills.analyze import extract_knowledge
                    knowledge = await extract_knowledge.ainvoke({"content": content})
                    concepts = knowledge.get("concepts", [])
                except Exception:
                    pass

            # Tag
            tags = results[1] if isinstance(results[1], dict) else {}

            # Summary
            summary_data = results[2] if isinstance(results[2], dict) else {}

            # Relation discovery (needs concepts first)
            relations = []
            try:
                from openlearning.skills.analyze import discover_relations
                relations = await discover_relations.ainvoke({
                    "new_concepts": concepts,
                    "existing_graph": knowledge_graph,
                })
            except Exception:
                pass

            title = resource.get("title", "")[:40]
            print(f"[Analyzer] ✓ {title}: {len(concepts)} 概念, {tags.get('difficulty', '?')}")

            return {
                **resource,
                "knowledge": {"concepts": concepts},
                "tags": tags,
                "summary": summary_data.get("summary", ""),
                "key_points": summary_data.get("key_points", []),
                "one_line_summary": summary_data.get("one_line_summary", ""),
                "analysis_level": "full",
                "_concepts": concepts,
                "_relations": relations,
            }

    # Process all resources concurrently (up to 8 at a time)
    print(f"[Analyzer] 并发分析 {len(all_high)} 条资源 (并发=8)...")
    analyzed = list(await asyncio.gather(*[_analyze_one(r) for r in all_high]))

    # Collect concepts and relations from results
    for result in analyzed:
        all_concepts.extend(result.pop("_concepts", []))
        all_relations.extend(result.pop("_relations", []))

    # Mark fetch_rest as full analysis too
    for resource in fetch_rest:
        if resource not in analyzed:
            resource["analysis_level"] = "full"

    # Merge into knowledge graph
    updated_graph = _merge_into_graph(knowledge_graph, all_concepts, all_relations)

    # Calculate average quality
    all_resources = analyzed + low_score
    scores = [r.get("quality_score", 0) for r in all_resources if r.get("quality_score")]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    # Persist analyzed resources
    await _persist_analyzed(all_resources)

    return {
        "analyzed_resources": all_resources,
        "extracted_concepts": all_concepts,
        "concept_relations": all_relations,
        "knowledge_graph": updated_graph,
        "avg_quality_score": round(avg_score, 2),
        "current_agent": "analyzer",
    }


async def _fetch_contents(resources: list[dict]) -> list[dict]:
    """Fetch full page content for top resources using fetch skill."""
    from openlearning.skills.fetch import fetch_page

    async def _fetch_one(r: dict) -> dict:
        url = r.get("url", "")
        if not url:
            r["full_content"] = r.get("snippet", "")
            return r
        try:
            result = await fetch_page.ainvoke({"url": url})
            if result.get("success") and result.get("content"):
                r["full_content"] = result["content"][:15000]  # Cap at 15k chars
                r["fetched_title"] = result.get("title", r.get("title", ""))
                print(f"[Analyzer] ✓ 抓取成功: {url[:60]} ({len(r['full_content'])} 字符)")
            else:
                r["full_content"] = r.get("snippet", "")
                print(f"[Analyzer] ✗ 抓取失败: {url[:60]}")
        except Exception as e:
            r["full_content"] = r.get("snippet", "")
            print(f"[Analyzer] ✗ 抓取异常: {url[:60]} - {e}")
        return r

    # Fetch in parallel with concurrency limit
    import asyncio
    semaphore = asyncio.Semaphore(4)

    async def _bounded_fetch(r: dict) -> dict:
        async with semaphore:
            return await _fetch_one(r)

    return await asyncio.gather(*[_bounded_fetch(r) for r in resources])


async def _llm_extract(content: str) -> dict:
    """LLM knowledge extraction."""
    try:
        from openlearning.skills.analyze import llm_extract_knowledge
        return await llm_extract_knowledge.ainvoke({
            "content": content[:6000],
            "existing_concepts": [],
        })
    except Exception:
        return {"concepts": []}


async def _llm_tag(content: str, title: str = "") -> dict:
    """LLM tagging."""
    try:
        from openlearning.skills.analyze import llm_tag
        return await llm_tag.ainvoke({"content": content[:4000], "title": title})
    except Exception:
        return {}


async def _llm_summarize(content: str) -> dict:
    """LLM summary."""
    try:
        from openlearning.skills.analyze import llm_summarize
        return await llm_summarize.ainvoke({
            "content": content[:6000],
            "lang": "zh",
            "max_length": 500,
        })
    except Exception:
        return {}


async def _rule_based_scoring(resources: list[dict]) -> list[dict]:
    """Apply rule-based scoring to all resources."""
    from openlearning.skills.analyze import score

    scored = []
    for r in resources:
        try:
            content = r.get("snippet", "") + " " + r.get("title", "")
            score_result = await score.ainvoke({
                "content": content,
                "metadata": {
                    "source": r.get("source", ""),
                    "published": r.get("published", ""),
                    "stars": r.get("stars", 0),
                    "url": r.get("url", ""),
                },
            })
            r["quality_score"] = score_result.get("final_score", 0.0)
            r["quality_scores"] = score_result.get("scores", {})
        except Exception:
            r["quality_score"] = 5.0  # default

        scored.append(r)

    return scored


def _merge_into_graph(graph: dict, concepts: list[dict], relations: list[dict]) -> dict:
    """Merge new concepts and relations into the knowledge graph."""
    existing_nodes = graph.get("nodes", [])
    existing_edges = graph.get("edges", [])

    # Dedup nodes by id
    existing_ids = {n.get("id", "") for n in existing_nodes}
    new_nodes = []
    for c in concepts:
        node_id = c.get("name", "").lower().replace(" ", "_")
        if node_id not in existing_ids:
            new_nodes.append({
                "id": node_id,
                "name": c.get("name", ""),
                "type": c.get("type", "concept"),
                "definition": c.get("definition", ""),
                "difficulty": c.get("difficulty", "intermediate"),
                "importance": 0.5,
            })
            existing_ids.add(node_id)

    # Dedup edges
    edge_keys = {(e.get("from", ""), e.get("to", "")) for e in existing_edges}
    new_edges = []
    for r in relations:
        key = (r.get("from", ""), r.get("to", ""))
        if key not in edge_keys:
            new_edges.append(r)
            edge_keys.add(key)

    return {
        "nodes": existing_nodes + new_nodes,
        "edges": existing_edges + new_edges,
        "topic": graph.get("topic", ""),
    }


async def _persist_analyzed(resources: list[dict]) -> None:
    """Persist analyzed resources to database."""
    try:
        from openlearning.skills.persist import save_resource

        for r in resources:
            try:
                await save_resource.ainvoke({"resource": r})
            except Exception:
                continue
    except Exception:
        pass
