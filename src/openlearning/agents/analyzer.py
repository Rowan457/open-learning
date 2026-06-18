"""Analyzer Agent — content analysis and knowledge extraction subgraph.

Two-stage analysis: rule-based pre-filter → LLM deep analysis for high-score resources.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


async def analyzer_agent(state: AgentState) -> dict[str, Any]:
    """Analyzer subgraph: two-stage analysis pipeline.

    Stage 1: Rule-based scoring (zero LLM cost)
    Stage 2: Deep analysis for high-score resources

    Reads: raw_resources, knowledge_graph, avoid_list
    Writes: analyzed_resources, extracted_concepts, concept_relations, knowledge_graph
    """
    resources = state.get("raw_resources", [])
    knowledge_graph = state.get("knowledge_graph", {})
    avoid_list = set(state.get("avoid_list", []))

    if not resources:
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

    # ── Stage 2: Deep analysis for high-score resources ──────
    analyzed = []
    all_concepts = []
    all_relations = []

    for resource in high_score:
        content = resource.get("snippet", "") + " " + resource.get("title", "")

        # Knowledge extraction
        try:
            from openlearning.skills.analyze import extract_knowledge

            knowledge = await extract_knowledge.ainvoke({
                "content": content,
                "existing_concepts": [c.get("name", "") for c in all_concepts],
            })
            concepts = knowledge.get("concepts", [])
        except Exception:
            concepts = []

        # Relation discovery
        try:
            from openlearning.skills.analyze import discover_relations

            relations = await discover_relations.ainvoke({
                "new_concepts": concepts,
                "existing_graph": knowledge_graph,
            })
        except Exception:
            relations = []

        # Tagging
        try:
            from openlearning.skills.analyze import tag

            tags = await tag.ainvoke({"content": content})
        except Exception:
            tags = {}

        # Summary
        try:
            from openlearning.skills.analyze import summarize

            summary_data = await summarize.ainvoke({"content": content})
        except Exception:
            summary_data = {}

        all_concepts.extend(concepts)
        all_relations.extend(relations)

        analyzed.append({
            **resource,
            "knowledge": {"concepts": concepts},
            "tags": tags,
            "summary": summary_data.get("summary", ""),
            "key_points": summary_data.get("key_points", []),
            "analysis_level": "full",
        })

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
