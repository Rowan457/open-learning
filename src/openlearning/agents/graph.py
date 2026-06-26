"""Main graph compilation — three-layer nested LangGraph architecture.

三层嵌套架构：
- 第一层（主图）：端到端流程 — preprocess → supervisor 子图 → postprocess
- 第二层（Supervisor 子图）：决策循环 + 并行 Worker 调度
- 第三层（Worker 子图）：ReAct 循环执行具体任务

通过子图嵌套实现分层编排，每层独立编译、独立状态、通过字段对齐通信。
"""

from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, START, StateGraph

from openlearning.agents.state import AgentInputState, AgentState
from openlearning.log import get_logger
from openlearning.monitoring.tracer import traceable

logger = get_logger("Graph")


# ── 前置处理：memory + planner ──────────────────────────────

@traceable("preprocess")
async def _preprocess(state: AgentState) -> dict[str, Any]:
    """前置处理：查询用户记忆 → 生成研究计划。

    串行执行 memory_agent 和 planner_agent，为 Supervisor 提供研究上下文。
    """
    from openlearning.agents.memory import memory_agent
    from openlearning.agents.planner import planner_agent

    logger.info("━━━ Preprocess: 记忆查询 + 研究规划 ━━━")

    # 1. 查询用户记忆
    memory_result = await memory_agent(state)
    logger.info("记忆查询完成: %s", list(memory_result.keys()))

    # 2. 生成研究计划（合并 memory 结果到 state）
    planner_state = {**state, **memory_result}
    planner_result = await planner_agent(planner_state)
    logger.info("研究规划完成: %s 个搜索词", len(planner_result.get("search_queries", [])))

    # 3. 构建研究简报
    user_request = state.get("user_request", "")
    knowledge_graph = planner_result.get("knowledge_graph", {})
    search_queries = planner_result.get("search_queries", [])
    user_memory = memory_result.get("user_memory", {})

    research_brief = _build_research_brief(user_request, knowledge_graph, search_queries, user_memory)

    return {
        **memory_result,
        **planner_result,
        "research_brief": research_brief,
        "current_agent": "preprocess",
    }


def _build_research_brief(
    user_request: str,
    knowledge_graph: dict,
    search_queries: list[str],
    user_memory: dict,
) -> str:
    """构建研究简报，供 Supervisor 使用。"""
    parts = [f"# 研究任务\n\n{user_request}\n"]

    nodes = knowledge_graph.get("nodes", [])
    if nodes:
        concepts = ", ".join(n.get("name", "") for n in nodes[:10])
        parts.append(f"## 核心概念\n{concepts}\n")

    if search_queries:
        queries = "\n".join(f"- {q}" for q in search_queries[:10])
        parts.append(f"## 初始搜索词\n{queries}\n")

    gaps = user_memory.get("gaps", [])
    if gaps:
        gap_names = [g.get("name", g.get("concept_id", "")) if isinstance(g, dict) else str(g) for g in gaps[:5]]
        parts.append(f"## 知识缺口\n{', '.join(gap_names)}\n")

    return "\n".join(parts)


# ── 知识点提取 ──────────────────────────────────────────────

async def _extract_concepts_from_resources(
    resources: list[dict], existing_graph: dict
) -> dict[str, Any]:
    """从资源中提取知识点，返回新发现的节点和边。"""
    import asyncio
    from openlearning.llm import achat_json

    semaphore = asyncio.Semaphore(5)

    async def _extract_one(resource: dict) -> dict:
        async with semaphore:
            content = resource.get("summary", "") or resource.get("snippet", "")
            title = resource.get("title", "")
            if len(content) < 30:
                return {"concepts": [], "relations": []}
            prompt = f"""从以下资源中提取知识点和它们之间的关系。

标题: {title}
内容: {content[:3000]}

以 JSON 格式输出:
{{"concepts": [{{"name": "概念名", "definition": "一句话定义", "difficulty": "beginner/intermediate/advanced"}}], "relations": [{{"from": "概念A", "to": "概念B", "type": "prerequisite/related/extends"}}]}}"""
            try:
                result = await achat_json(
                    messages=[{"role": "user", "content": prompt}],
                    tier="lite",
                    temperature=0.2,
                )
                return result if isinstance(result, dict) else {"concepts": [], "relations": []}
            except Exception:
                return {"concepts": [], "relations": []}

    # 并行提取（最多处理 top 20 个有摘要的资源）
    eligible = [r for r in resources if (r.get("summary") or r.get("snippet")) and len(r.get("summary", "") or r.get("snippet", "")) > 30]
    eligible.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    results = await asyncio.gather(*[_extract_one(r) for r in eligible[:20]])

    # 合并去重
    existing_ids = {n.get("id") for n in existing_graph.get("nodes", [])}
    existing_edge_keys = {(e.get("from", ""), e.get("to", "")) for e in existing_graph.get("edges", [])}

    new_nodes = []
    new_edges = []
    seen_ids = set()

    for r in results:
        for c in r.get("concepts", []):
            cid = c.get("name", "").lower().replace(" ", "_")
            if cid and cid not in existing_ids and cid not in seen_ids:
                new_nodes.append({
                    "id": cid,
                    "name": c.get("name", ""),
                    "type": "concept",
                    "definition": c.get("definition", ""),
                    "difficulty": c.get("difficulty", "intermediate"),
                    "importance": 0.5,
                })
                seen_ids.add(cid)
        for rel in r.get("relations", []):
            key = (rel.get("from", "").lower().replace(" ", "_"), rel.get("to", "").lower().replace(" ", "_"))
            if key[0] and key[1] and key not in existing_edge_keys:
                new_edges.append({
                    "from": key[0],
                    "to": key[1],
                    "type": rel.get("type", "related"),
                    "weight": 0.5,
                })
                existing_edge_keys.add(key)

    return {"new_nodes": new_nodes, "new_edges": new_edges}


# ── 后置处理：采集 + builder ──────────────────────────────────

@traceable("postprocess")
async def _postprocess(state: AgentState) -> dict[str, Any]:
    """后置处理：采集资源 → 提取知识点 → 生成学习系统。

    1. 从数据库加载 Worker 采集的资源（如果有 project_id）
    2. 如果没有资源，使用 collector_agent 采集
    3. 从资源中提取知识点，扩展知识图谱
    4. 使用 builder_agent 生成知识图谱驱动的学习系统
    """
    from openlearning.agents.builder import builder_agent
    from openlearning.agents.collector import collector_agent

    logger.info("━━━ Postprocess: 采集资源 + 生成学习系统 ━━━")

    # 1. 检查 Supervisor 阶段是否已采集资源
    raw_resources = state.get("raw_resources", [])
    project_id = state.get("project_id", "")

    # 2. 如果没有资源但有 project_id，从数据库加载（Worker 已通过 save_resource 持久化）
    if not raw_resources and project_id:
        try:
            from openlearning.database import get_resources_by_project
            db_resources = get_resources_by_project(project_id)
            if db_resources:
                raw_resources = [
                    {
                        "url": r.url, "title": r.title, "source": r.source,
                        "summary": r.summary, "quality_score": r.quality_score,
                        "resource_type": r.resource_type, "snippet": r.summary or "",
                        "project_id": r.project_id,
                    }
                    for r in db_resources
                ]
                state = {**state, "raw_resources": raw_resources}
                logger.info("从数据库加载 %s 条已有资源", len(raw_resources))
        except Exception as e:
            logger.warning("从数据库加载资源失败: %s", e)

    # 3. 如果仍然没有资源，启动独立采集
    if not raw_resources:
        logger.info("研究阶段未采集到资源，启动独立采集...")
        collect_result = await collector_agent(state)
        state = {**state, **collect_result}
        logger.info("采集完成: %s 条资源", len(collect_result.get("raw_resources", [])))

    # 4. 从资源中提取知识点，扩展知识图谱
    raw_resources = state.get("raw_resources", [])
    knowledge_graph = state.get("knowledge_graph", {})
    if raw_resources:
        extracted = await _extract_concepts_from_resources(raw_resources, knowledge_graph)
        if extracted.get("new_nodes"):
            existing_ids = {n.get("id") for n in knowledge_graph.get("nodes", [])}
            new_nodes = [n for n in extracted["new_nodes"] if n.get("id") not in existing_ids]
            if new_nodes:
                knowledge_graph["nodes"] = knowledge_graph.get("nodes", []) + new_nodes
                knowledge_graph["edges"] = knowledge_graph.get("edges", []) + extracted.get("new_edges", [])
                state = {**state, "knowledge_graph": knowledge_graph}
                logger.info("从资源中提取 %s 个新知识点", len(new_nodes))

    # 5. 生成学习系统
    result = await builder_agent(state)
    logger.info("学习系统生成完成: %s", list(result.keys()))

    return {
        **result,
        "raw_resources": state.get("raw_resources", []),
        "collected_count": state.get("collected_count", 0),
        "sources_queried": state.get("sources_queried", []),
        "current_agent": "postprocess",
        "status": "done",
    }


def compile_graph():
    """编译完整的三层嵌套图。

    从底层开始编译：
    1. Worker 子图（使用 Worker 工具）
    2. Supervisor 子图（使用 Supervisor 工具 + Worker 子图）
    3. 主图（preprocess → supervisor 子图 → postprocess）
    """
    from openlearning.agents.tools import get_supervisor_tools, get_worker_tools
    from openlearning.agents.subgraphs.worker import build_worker_subgraph
    from openlearning.monitoring.tracer import init_tracing

    # 确保 LangSmith 追踪在编译前初始化
    init_tracing()
    from openlearning.agents.subgraphs.supervisor import build_supervisor_subgraph
    from openlearning.config import get_config

    cfg = get_config()

    # 读取研究配置（带默认值）
    research_cfg = getattr(cfg, "research", None)
    max_concurrent = getattr(research_cfg, "max_concurrent_workers", 3) if research_cfg else 3
    max_iterations = getattr(research_cfg, "max_research_iterations", 5) if research_cfg else 5
    max_tool_calls = getattr(research_cfg, "max_worker_tool_calls", 10) if research_cfg else 10

    # ── 第三层：Worker 子图 ──────────────────────────────────
    worker_tools = get_worker_tools()
    worker_subgraph = build_worker_subgraph(
        tools=worker_tools,
        max_tool_calls=max_tool_calls,
    )
    logger.info("Worker 子图编译完成 (%s 个工具)", len(worker_tools))

    # ── 第二层：Supervisor 子图 ──────────────────────────────
    supervisor_tools = get_supervisor_tools()
    supervisor_subgraph = build_supervisor_subgraph(
        worker_subgraph=worker_subgraph,
        supervisor_tools=supervisor_tools,
        max_concurrent=max_concurrent,
        max_iterations=max_iterations,
    )
    logger.info("Supervisor 子图编译完成 (max_concurrent=%s, max_iterations=%s)", max_concurrent, max_iterations)

    # ── 第一层：主图 ────────────────────────────────────────
    graph = StateGraph(AgentState, input=AgentInputState)

    graph.add_node("preprocess", _preprocess)
    graph.add_node("supervisor", supervisor_subgraph)  # 子图嵌入
    graph.add_node("postprocess", _postprocess)

    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "supervisor")
    graph.add_edge("supervisor", "postprocess")
    graph.add_edge("postprocess", END)

    compiled = graph.compile()
    logger.info("三层嵌套图编译完成")

    return compiled


# ── 便捷运行器 ──────────────────────────────────────────────

@traceable("run_pipeline")
async def run_pipeline(
    user_request: str,
    user_profile: dict | None = None,
    max_iterations: int = 3,
    project_id: str | None = None,
    incremental: bool = False,
    since_days: int | None = None,
) -> dict[str, Any]:
    """运行完整的三层嵌套流水线。

    Args:
        user_request: 用户学习请求，如 "我想学 Rust"
        user_profile: 用户画像，如 {"level": "beginner", "lang": ["zh", "en"]}
        max_iterations: 最大迭代次数
        project_id: 指定项目 ID（更新已有项目时使用）
        incremental: 增量模式，跳过已有资源
        since_days: 只搜索最近 N 天的内容

    Returns:
        最终状态，包含所有 agent 输出
    """
    compiled = compile_graph()

    initial_state: AgentInputState = {
        "user_request": user_request,
        "user_profile": user_profile or {"level": "beginner", "lang": ["zh", "en"]},
        "max_iterations": max_iterations,
        "project_id": project_id or "",
        "incremental": incremental,
    }
    if since_days is not None:
        initial_state["since_days"] = since_days

    logger.info("━━━ 开始执行: %s ━━━", user_request)
    start_time = time.time()

    final_state = await compiled.ainvoke(initial_state)

    elapsed = time.time() - start_time
    logger.info("━━━ 执行完成 (%.1fs) ━━━", elapsed)

    # 打印摘要
    _print_summary(final_state, elapsed)

    return final_state


def _print_summary(state: dict, elapsed: float) -> None:
    """打印执行摘要。"""
    raw_count = len(state.get("raw_resources", []))
    analyzed_count = len(state.get("analyzed_resources", []))
    evaluation = state.get("evaluation", {})
    notes = state.get("notes", [])

    print(f"\n{'='*50}")
    print(f"执行摘要 ({elapsed:.1f}s)")
    print(f"{'='*50}")
    print(f"  采集资源: {raw_count} 条")
    print(f"  分析资源: {analyzed_count} 条")
    print(f"  研究笔记: {len(notes)} 条")
    if evaluation:
        print(f"  评估通过: {evaluation.get('pass', 'N/A')}")
    learning_system = state.get("learning_system", {})
    if learning_system:
        print(f"  学习系统: 已生成")
    print(f"{'='*50}\n")
