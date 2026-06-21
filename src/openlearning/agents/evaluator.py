"""Evaluation Engine — rule-based quality/coverage/diversity checks.

No LLM cost — pure rule engine.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


async def evaluator_engine(state: AgentState) -> dict[str, Any]:
    """Evaluation Engine: rule-driven quality/coverage/diversity/freshness checks.

    Reads: analyzed_resources, knowledge_graph, iteration
    Writes: evaluation, iteration
    """
    resources = state.get("analyzed_resources", [])
    graph = state.get("knowledge_graph", {})
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    # 1. Quality check (avg ≥ 5.0, single ≥ 3.0)
    quality = _check_quality(resources, min_avg=5.0, min_single=3.0)

    # 2. Coverage check (≥ 60% nodes covered)
    coverage = _check_coverage(graph, resources)

    # 3. Diversity check (≥ 3 types)
    diversity = _check_diversity(resources, min_types=3)

    # 4. Freshness check (≥ 20% recent among dated resources)
    freshness = _check_freshness(resources, min_recent_ratio=0.2)

    # 5. Overall judgment
    all_passed = all([quality["pass"], coverage["pass"], diversity["pass"], freshness["pass"]])
    forced_pass = iteration >= max_iterations

    return {
        "evaluation": {
            "pass": all_passed or forced_pass,
            "quality": quality,
            "coverage": coverage,
            "diversity": diversity,
            "freshness": freshness,
            "forced_pass": forced_pass,
        },
        "iteration": iteration + 1,
        "current_agent": "evaluator",
    }


def _check_quality(resources: list[dict], min_avg: float = 5.0, min_single: float = 3.0) -> dict:
    """Check quality scores meet thresholds.

    阈值说明:
    - min_avg=5.0: 平均分 5.0 即可（满分 10）
    - min_single=3.0: 单个资源最低 3.0
    """
    if not resources:
        return {"pass": False, "reason": "No resources", "avg": 0.0, "low_count": 0}

    scores = [r.get("quality_score", 0) for r in resources]
    avg = sum(scores) / len(scores) if scores else 0.0
    low_count = sum(1 for s in scores if s < min_single)

    passed = avg >= min_avg and low_count == 0

    return {
        "pass": passed,
        "avg": round(avg, 2),
        "low_count": low_count,
        "reason": f"Avg={avg:.1f} (need ≥{min_avg}), {low_count} below {min_single}",
    }


def _check_coverage(graph: dict, resources: list[dict]) -> dict:
    """Check knowledge graph nodes have resource coverage.

    Uses keyword-based fuzzy matching: split node name into words,
    check if any keyword appears in resource title/snippet.
    """
    nodes = graph.get("nodes", [])
    if not nodes:
        return {"pass": True, "reason": "No knowledge graph", "covered": 0, "total": 0}

    # Build combined resource text for matching
    all_resource_text = ""
    for r in resources:
        all_resource_text += " " + r.get("title", "") + " " + r.get("snippet", "")
    all_resource_text = all_resource_text.lower()

    covered = 0
    uncovered = []
    for node in nodes:
        node_name = node.get("name", "").lower()
        node_id = node.get("id", "").lower().replace("_", " ")

        # Split name into keywords for fuzzy matching
        keywords = [kw for kw in node_name.split() if len(kw) > 2]
        if not keywords:
            keywords = [node_name]

        # Check: full name match OR any keyword match
        is_covered = (
            node_name in all_resource_text
            or node_id in all_resource_text
            or any(kw in all_resource_text for kw in keywords)
        )

        if is_covered:
            covered += 1
        else:
            uncovered.append(node.get("name", node.get("id", "")))

    total = len(nodes)
    ratio = covered / total if total > 0 else 0.0
    passed = ratio >= 0.6  # 60% coverage threshold

    return {
        "pass": passed,
        "covered": covered,
        "total": total,
        "ratio": round(ratio, 2),
        "uncovered": uncovered[:10],
        "reason": f"{covered}/{total} nodes covered ({ratio:.0%}), need ≥60%",
    }


def _check_diversity(resources: list[dict], min_types: int = 3) -> dict:
    """Check resource type diversity."""
    if not resources:
        return {"pass": False, "reason": "No resources", "types": [], "count": 0}

    types = set()
    for r in resources:
        # Infer type from source or resource_type
        rtype = r.get("resource_type", r.get("source", "article"))
        types.add(rtype)

    passed = len(types) >= min_types

    return {
        "pass": passed,
        "types": list(types),
        "count": len(types),
        "reason": f"{len(types)} types ({', '.join(types)}), need ≥{min_types}",
    }


def _check_freshness(resources: list[dict], min_recent_ratio: float = 0.2) -> dict:
    """Check that enough resources are recent (within 2 years).

    逻辑:
    - 有日期且在 2 年内 → recent
    - 有日期且超过 2 年 → old
    - 无日期 → unknown（不计入分母）
    - 只在有日期的资源中计算 recent 比例
    """
    if not resources:
        return {"pass": False, "reason": "No resources", "recent_ratio": 0.0}

    from datetime import datetime, timedelta

    two_years_ago = datetime.utcnow() - timedelta(days=730)
    recent_count = 0
    old_count = 0
    unknown_count = 0

    for r in resources:
        published = r.get("published", "")
        if published:
            try:
                pub_date = datetime.strptime(published[:10], "%Y-%m-%d")
                if pub_date > two_years_ago:
                    recent_count += 1
                else:
                    old_count += 1
            except (ValueError, TypeError):
                unknown_count += 1
        else:
            unknown_count += 1

    # 只在有日期的资源中计算比例
    dated_count = recent_count + old_count
    if dated_count > 0:
        ratio = recent_count / dated_count
    else:
        # 没有资源有日期，假设都是新的（避免过度惩罚）
        ratio = 1.0

    passed = ratio >= min_recent_ratio

    return {
        "pass": passed,
        "recent_count": recent_count,
        "old_count": old_count,
        "unknown_count": unknown_count,
        "total": len(resources),
        "ratio": round(ratio, 2),
        "reason": f"{recent_count}/{dated_count} dated resources recent ({ratio:.0%}), {unknown_count} unknown dates",
    }
