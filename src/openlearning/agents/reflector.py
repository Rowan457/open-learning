"""Reflector Agent — strategy reflection subgraph.

Uses LLM (or rule-based fallback) to reflect on evaluation results and suggest improvements.
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


async def reflector_agent(state: AgentState) -> dict[str, Any]:
    """Reflector subgraph: analyze evaluation → strategy adjustment suggestions.

    Reads: evaluation, knowledge_graph, user_memory
    Writes: reflection
    """
    evaluation = state.get("evaluation", {})
    graph = state.get("knowledge_graph", {})
    memory = state.get("user_memory", {})
    iteration = state.get("iteration", 0)

    # Rule-based reflection (no LLM cost)
    reflection = _rule_based_reflection(evaluation, graph, memory, iteration)

    return {
        "reflection": reflection,
        "current_agent": "reflector",
    }


def _rule_based_reflection(
    evaluation: dict,
    graph: dict,
    memory: dict,
    iteration: int,
) -> dict:
    """Generate strategy adjustment suggestions based on evaluation results."""
    suggestions = []
    search_adjustments = []
    priority_adjustments = []

    quality = evaluation.get("quality", {})
    coverage = evaluation.get("coverage", {})
    diversity = evaluation.get("diversity", {})
    freshness = evaluation.get("freshness", {})

    # Quality issues
    if not quality.get("pass", True):
        avg = quality.get("avg", 0)
        if avg < 4.0:
            suggestions.append("资源质量严重不足，建议更换搜索源或使用更精确的关键词")
            search_adjustments.append("add site filter: github.com OR arxiv.org")
        elif avg < 6.0:
            suggestions.append("资源质量略低，建议增加权威来源的权重")
            search_adjustments.append("add 'official' OR 'documentation' to queries")

    # Coverage issues
    if not coverage.get("pass", True):
        uncovered = coverage.get("uncovered", [])
        if uncovered:
            suggestions.append(f"以下知识节点缺少资源: {', '.join(uncovered[:5])}")
            for concept in uncovered[:3]:
                search_adjustments.append(f"search specifically for: {concept}")

    # Diversity issues
    if not diversity.get("pass", True):
        current_types = diversity.get("types", [])
        missing = []
        for t in ["article", "video", "paper", "repo"]:
            if t not in current_types:
                missing.append(t)
        if missing:
            suggestions.append(f"缺少以下类型资源: {', '.join(missing)}")
            for t in missing:
                if t == "video":
                    search_adjustments.append("add youtube search")
                elif t == "paper":
                    search_adjustments.append("add arxiv search")
                elif t == "repo":
                    search_adjustments.append("add github search")

    # Freshness issues
    if not freshness.get("pass", True):
        suggestions.append("资源时效性不足，建议增加时间限定搜索")
        search_adjustments.append("add '2025 OR 2026' to queries")

    # Iteration-based adjustments
    if iteration >= 2:
        suggestions.append("已进行多轮采集，建议降低质量阈值或接受当前结果")
        priority_adjustments.append("lower quality threshold to 5.0")

    # Memory-based adjustments
    if similar := memory.get("similar_project"):
        suggestions.append(f"发现类似历史项目 '{similar.get('title', '')}'，可参考其资源")

    return {
        "suggestions": suggestions,
        "search_adjustments": search_adjustments,
        "priority_adjustments": priority_adjustments,
        "should_continue": iteration < 3 and len(suggestions) > 0,
        "iteration": iteration,
    }
