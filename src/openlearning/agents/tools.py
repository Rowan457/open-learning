"""Supervisor 工具定义 — 用于三层嵌套架构的 Supervisor 决策。

工具分类：
- ConductResearch: 委派研究任务给 Worker（由 Supervisor 子图拦截处理）
- ResearchComplete: 信号工具，表示研究完成（由 Supervisor 子图拦截处理）
- think_tool: 反思工具，记录思考过程（无外部副作用）
- EvaluateQuality: 运行评估引擎（调用 evaluator 逻辑）
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from openlearning.log import get_logger

logger = get_logger("Tools")


@tool
def ConductResearch(topic: str) -> str:
    """委派一个具体的研究子任务给 Worker 执行。

    Worker 会使用搜索工具收集信息、分析内容、返回压缩后的研究结果。
    每个 topic 应该是明确、具体的研究方向。

    Args:
        topic: 具体的研究主题，如 "Rust ownership 模型教程"、"Rust 错误处理最佳实践"
    """
    # 这是一个占位实现 — Supervisor 子图会拦截此工具调用并委派给 Worker
    return f"Research task queued: {topic}"


@tool
def ResearchComplete() -> str:
    """表示研究已完成，可以生成最终报告。

    当你认为已经收集了足够信息时调用此工具。
    """
    # 这是一个信号工具 — Supervisor 子图会拦截此调用并结束研究循环
    return "Research complete"


@tool
def think_tool(reflection: str) -> str:
    """记录你的思考和反思。用于分析当前进展、决定下一步策略。

    不会产生外部副作用，只是记录你的推理过程。

    Args:
        reflection: 你的思考内容，如对当前研究进展的评估、下一步计划等
    """
    logger.info("Supervisor 反思: %s", reflection[:200])
    return f"Reflection recorded: {reflection}"


@tool
async def EvaluateQuality(resources: list[dict], knowledge_graph: dict) -> dict:
    """评估已收集资源的质量、覆盖度、多样性和时效性。

    Args:
        resources: 已分析的资源列表
        knowledge_graph: 当前知识图谱
    """
    from openlearning.agents.evaluator import (
        _check_coverage,
        _check_diversity,
        _check_freshness,
        _check_quality,
    )

    quality = _check_quality(resources, min_avg=5.0, min_single=3.0)
    coverage = _check_coverage(knowledge_graph, resources)
    diversity = _check_diversity(resources, min_types=3)
    freshness = _check_freshness(resources, min_recent_ratio=0.2)

    all_passed = all([quality["pass"], coverage["pass"], diversity["pass"], freshness["pass"]])

    result = {
        "pass": all_passed,
        "quality": quality,
        "coverage": coverage,
        "diversity": diversity,
        "freshness": freshness,
    }

    logger.info(
        "评估结果: pass=%s, quality=%.1f, coverage=%.0f%%, types=%s",
        all_passed,
        quality.get("avg", 0),
        coverage.get("ratio", 0) * 100,
        diversity.get("count", 0),
    )

    return result


def get_supervisor_tools() -> list:
    """获取 Supervisor 可用的工具列表。"""
    return [ConductResearch, ResearchComplete, think_tool, EvaluateQuality]


def get_worker_tools() -> list:
    """获取 Worker 可用的工具列表（搜索 + 抓取 + 分析 + 持久化 + 插件）。"""
    from openlearning.tools.search import (
        arxiv_search,
        github_search,
        web_search,
        youtube_search,
    )
    from openlearning.tools.fetch import fetch_page
    from openlearning.tools.analyze import (
        extract_knowledge,
        llm_summarize,
        summarize,
    )
    from openlearning.tools.persist import save_resource

    tools = [
        web_search,
        arxiv_search,
        youtube_search,
        github_search,
        fetch_page,
        save_resource,
        summarize,
        extract_knowledge,
        llm_summarize,
        plugin_search,
    ]

    return tools


@tool
async def plugin_search(query: str, max_results: int = 15) -> list[dict]:
    """使用已启用的插件搜索资源。搜索所有已启用的自定义数据源（如 RSS、豆瓣、自定义 API 等）。

    Args:
        query: 搜索关键词
        max_results: 最大返回数量
    """
    try:
        from openlearning.plugins.manager import PluginManager
        pm = PluginManager()
        pm.discover()
        results = await pm.search_all(query, max_results=max_results)
        logger.info("插件搜索 '%s': %s 条结果", query, len(results))
        return results
    except Exception as e:
        logger.warning("插件搜索失败: %s", e)
        return []
