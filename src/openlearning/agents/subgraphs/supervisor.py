"""Supervisor 子图 — 决策循环 + 并行 Worker 调度。

Supervisor 负责：
1. 分析研究任务，分解为子任务
2. 通过 ConductResearch 工具并行委派给 Worker
3. 评估 Worker 返回的结果
4. 决定继续研究或结束

设计要点：
- Supervisor 只决策不执行，实际工作交给 Worker
- asyncio.gather 实现真正的并行 Worker 调度
- max_concurrent_workers 限制并发数，防止资源耗尽
- think_tool 是伪工具，只记录反思内容，不产生外部副作用
- 退出条件三选一：超迭代 / 无工具调用 / 调用 ResearchComplete
"""

from __future__ import annotations

import asyncio
from typing import Sequence

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from openlearning.agents.prompts import (
    SUPERVISOR_INIT_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
    format_knowledge_graph_summary,
    format_user_preferences,
)
from openlearning.agents.state import SupervisorState
from openlearning.log import get_logger

logger = get_logger("SupervisorSubgraph")


# ── Supervisor 决策节点 ─────────────────────────────────────

def _make_supervisor_fn(tools: Sequence[BaseTool], max_concurrent: int):
    """创建 Supervisor 决策节点（闭包）。"""

    async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command:
        """决策：调用工具 or 结束。"""
        from langchain_openai import ChatOpenAI
        from openlearning.config import get_config

        cfg = get_config()
        model = ChatOpenAI(
            model=cfg.llm.models.pro,  # Supervisor 用 Pro 模型
            api_key=cfg.llm.api_key,
            base_url=cfg.llm.base_url,
            temperature=0.2,
            max_tokens=cfg.llm.max_tokens,
        )
        model_with_tools = model.bind_tools(tools)

        # 构建系统提示词
        system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(max_concurrent=max_concurrent)

        # 首次调用时，注入研究简报
        messages = list(state.get("supervisor_messages", []))
        if not messages:
            # 初始化消息
            init_msg = SUPERVISOR_INIT_PROMPT.format(
                research_brief=state.get("research_brief", ""),
                knowledge_graph_summary=format_knowledge_graph_summary(
                    state.get("knowledge_graph", {})
                ),
                user_preferences="",  # 可从 state 中提取
            )
            messages = [HumanMessage(content=init_msg)]

        all_messages = [SystemMessage(content=system_prompt), *messages]

        try:
            response = await model_with_tools.ainvoke(all_messages)
            return Command(
                goto="supervisor_tools",
                update={
                    "supervisor_messages": [response],
                    "research_iterations": state.get("research_iterations", 0) + 1,
                },
            )
        except Exception as e:
            logger.error("Supervisor LLM 调用失败: %s", e)
            # 失败时结束研究
            return Command(
                goto=END,
                update={"notes": {"type": "override", "value": [f"Supervisor error: {e}"]}},
            )

    return supervisor


# ── Supervisor 工具执行节点 ─────────────────────────────────

def _make_supervisor_tools_fn(
    tools: Sequence[BaseTool],
    worker_subgraph,
    max_concurrent: int,
    max_iterations: int,
):
    """创建 Supervisor 工具执行节点（闭包）。"""
    tools_by_name = {t.name: t for t in tools}

    async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command:
        """执行工具调用：委派 Worker 或结束研究。"""
        most_recent = state.get("supervisor_messages", [])[-1] if state.get("supervisor_messages") else None

        # === 退出条件 ===
        exceeded = state.get("research_iterations", 0) > max_iterations
        no_calls = not most_recent or not hasattr(most_recent, "tool_calls") or not most_recent.tool_calls
        complete = any(
            tc.get("name") == "ResearchComplete"
            for tc in (most_recent.tool_calls if hasattr(most_recent, "tool_calls") and most_recent.tool_calls else [])
        )

        if exceeded or no_calls or complete:
            reason = "exceeded" if exceeded else ("no_calls" if no_calls else "complete")
            logger.info("Supervisor 结束研究: %s (iterations=%s)", reason, state.get("research_iterations", 0))
            return Command(
                goto=END,
                update={
                    "notes": {"type": "override", "value": _extract_notes(state)},
                    "status": "done",
                },
            )

        tool_calls = most_recent.tool_calls

        # === 处理 think_tool（反思，不产生外部副作用）===
        think_messages = []
        for tc in tool_calls:
            if tc.get("name") == "think_tool":
                reflection = tc.get("args", {}).get("reflection", "")
                logger.info("Supervisor 反思: %s", reflection[:200])
                think_messages.append(
                    ToolMessage(
                        content=f"Reflection recorded: {reflection}",
                        name="think_tool",
                        tool_call_id=tc["id"],
                    )
                )

        # === 处理 EvaluateQuality（同步执行）===
        for tc in tool_calls:
            if tc.get("name") == "EvaluateQuality":
                try:
                    tool = tools_by_name["EvaluateQuality"]
                    result = await tool.ainvoke(tc.get("args", {}))
                    think_messages.append(
                        ToolMessage(
                            content=str(result),
                            name="EvaluateQuality",
                            tool_call_id=tc["id"],
                        )
                    )
                except Exception as e:
                    think_messages.append(
                        ToolMessage(
                            content=f"Error: {e}",
                            name="EvaluateQuality",
                            tool_call_id=tc["id"],
                        )
                    )

        # === 处理 ConductResearch（并行委派 Worker）===
        conduct_calls = [tc for tc in tool_calls if tc.get("name") == "ConductResearch"]

        if conduct_calls:
            allowed = conduct_calls[:max_concurrent]
            overflow = conduct_calls[max_concurrent:]

            # 并行启动 Worker 子图
            async def _run_worker(call: dict) -> dict:
                topic = call.get("args", {}).get("topic", "")
                try:
                    result = await worker_subgraph.ainvoke({
                        "worker_messages": [HumanMessage(content=topic)],
                        "topic": topic,
                    })
                    return {"topic": topic, "output": result.get("compressed_output", "Error: no output")}
                except Exception as e:
                    logger.error("Worker 执行失败 [%s]: %s", topic, e)
                    return {"topic": topic, "output": f"Error: {e}"}

            logger.info("并行启动 %s 个 Worker: %s", len(allowed), [c.get("args", {}).get("topic", "")[:30] for c in allowed])
            results = await asyncio.gather(*[_run_worker(c) for c in allowed])

            # 构建返回消息
            for result, call in zip(results, allowed):
                think_messages.append(
                    ToolMessage(
                        content=result["output"],
                        name="ConductResearch",
                        tool_call_id=call["id"],
                    )
                )

            # 溢出任务返回错误
            for call in overflow:
                think_messages.append(
                    ToolMessage(
                        content=f"Error: 超出最大并发数 {max_concurrent}",
                        name="ConductResearch",
                        tool_call_id=call["id"],
                    )
                )

        return Command(
            goto="supervisor",
            update={"supervisor_messages": think_messages},
        )

    return supervisor_tools


# ── 辅助函数 ────────────────────────────────────────────────

def _extract_notes(state: SupervisorState) -> list[str]:
    """从 Supervisor 消息中提取研究笔记。"""
    notes = []
    for msg in state.get("supervisor_messages", []):
        if isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if msg.name == "ConductResearch" and not content.startswith("Error"):
                notes.append(content[:1000])
    return notes


# ── 子图构建 ────────────────────────────────────────────────

def build_supervisor_subgraph(
    worker_subgraph,
    supervisor_tools: Sequence[BaseTool],
    max_concurrent: int = 3,
    max_iterations: int = 5,
):
    """构建 Supervisor 子图。

    Args:
        worker_subgraph: 编译后的 Worker 子图实例
        supervisor_tools: Supervisor 可用的工具列表
        max_concurrent: 最大并发 Worker 数
        max_iterations: 最大研究迭代次数

    Returns:
        编译后的 Supervisor 子图
    """
    builder = StateGraph(SupervisorState)

    builder.add_node("supervisor", _make_supervisor_fn(supervisor_tools, max_concurrent))
    builder.add_node(
        "supervisor_tools",
        _make_supervisor_tools_fn(supervisor_tools, worker_subgraph, max_concurrent, max_iterations),
    )

    builder.add_edge(START, "supervisor")
    # supervisor_tools 内部通过 Command 动态路由回 supervisor 或 END

    return builder.compile()
