"""Reflector Agent — strategy reflection subgraph.

三个核心职责：
1. 是否继续搜索 (should_continue)
2. 缺什么资源 (missing_concepts)
3. 需要什么类型资源 (missing_types)
"""

from __future__ import annotations

from typing import Any

from openlearning.agents.state import AgentState


async def reflector_agent(state: AgentState) -> dict[str, Any]:
    """Reflector: 评估结果分析 → 三个决策输出。

    Reads: evaluation, knowledge_graph, user_memory, iteration, max_iterations
    Writes: reflection {should_continue, missing_concepts, missing_types, ...}
    """
    evaluation = state.get("evaluation", {})
    graph = state.get("knowledge_graph", {})
    memory = state.get("user_memory", {})
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    reflection = _reflect(evaluation, graph, memory, iteration, max_iterations)

    return {
        "reflection": reflection,
        "current_agent": "reflector",
    }


def _reflect(
    evaluation: dict,
    graph: dict,
    memory: dict,
    iteration: int,
    max_iterations: int,
) -> dict:
    """Reflector 核心逻辑：分析评估，输出三个决策。

    1. should_continue: 是否继续搜索
    2. missing_concepts: 缺什么资源（知识节点）
    3. missing_types: 需要什么类型资源（video/paper/repo/article）
    """
    quality = evaluation.get("quality", {})
    coverage = evaluation.get("coverage", {})
    diversity = evaluation.get("diversity", {})
    freshness = evaluation.get("freshness", {})
    all_passed = evaluation.get("pass", False)

    # ── 1. 缺什么资源 ────────────────────────────────────
    missing_concepts = _find_missing_concepts(coverage, graph)

    # ── 2. 需要什么类型资源 ──────────────────────────────
    missing_types = _find_missing_types(diversity)

    # ── 3. 是否继续搜索 ──────────────────────────────────
    should_continue, reason = _should_continue(
        all_passed=all_passed,
        iteration=iteration,
        max_iterations=max_iterations,
        missing_concepts=missing_concepts,
        missing_types=missing_types,
        quality=quality,
        freshness=freshness,
    )

    return {
        # 三个核心决策
        "should_continue": should_continue,
        "missing_concepts": missing_concepts,
        "missing_types": missing_types,
        # 辅助信息
        "reason": reason,
        "iteration": iteration,
        "quality_issue": not quality.get("pass", True),
        "freshness_issue": not freshness.get("pass", True),
    }


def _find_missing_concepts(coverage: dict, graph: dict) -> list[str]:
    """缺什么资源：从评估的覆盖率中提取未覆盖的知识节点。"""
    uncovered = coverage.get("uncovered", [])
    if uncovered:
        return uncovered

    # fallback: 对比图谱节点 vs 已有资源
    nodes = graph.get("nodes", [])
    if not nodes:
        return []

    # 返回所有节点（首次采集时全部算缺）
    return [n.get("name", n.get("id", "")) for n in nodes]


def _find_missing_types(diversity: dict) -> list[str]:
    """需要什么类型资源：对比当前已有类型 vs 期望类型。"""
    all_types = {"article", "video", "paper", "repo"}
    current = set(diversity.get("types", []))
    missing = all_types - current

    # 如果什么都没有（首次），全部需要
    if not current:
        return list(all_types)

    return sorted(missing)


def _should_continue(
    all_passed: bool,
    iteration: int,
    max_iterations: int,
    missing_concepts: list[str],
    missing_types: list[str],
    quality: dict,
    freshness: dict,
) -> tuple[bool, str]:
    """是否继续搜索：综合判断。"""
    # 全部达标 → 不继续
    if all_passed:
        return False, "all_passed"

    # 预算耗尽 → 不继续
    if iteration >= max_iterations:
        return False, "max_iterations_reached"

    # 有未覆盖的知识节点 → 继续
    if missing_concepts:
        return True, "missing_concepts"

    # 缺少资源类型 → 继续
    if missing_types:
        return True, "missing_types"

    # 质量不达标 → 继续（换关键词重搜）
    if not quality.get("pass", True):
        return True, "low_quality"

    # 时效性不达标 → 继续
    if not freshness.get("pass", True):
        return True, "low_freshness"

    return False, "no_actionable_fixes"
