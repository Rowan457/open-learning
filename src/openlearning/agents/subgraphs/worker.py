"""Worker 子图 — ReAct 循环 + 压缩节点。

Worker 负责执行具体的研究任务：使用工具收集信息 → 压缩结果 → 返回给 Supervisor。

设计要点：
- worker_messages 用 operator.add（纯追加），保留完整执行上下文供压缩使用
- output=WorkerOutputState 限制只返回压缩后的结果给 Supervisor
- 压缩节点是 Worker 的必经出口
- token 超限时渐进截断消息重试
"""

from __future__ import annotations

import asyncio
from typing import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from openlearning.agents.prompts import COMPRESS_HUMAN_PROMPT, COMPRESS_SYSTEM_PROMPT, WORKER_SYSTEM_PROMPT
from openlearning.agents.state import WorkerOutputState, WorkerState
from openlearning.log import get_logger

logger = get_logger("Worker")


# ── Worker 节点 ─────────────────────────────────────────────

def _make_worker_fn(tools: Sequence[BaseTool], worker_prompt: str):
    """创建 Worker 执行节点（闭包，捕获 tools 和 prompt）。"""

    async def worker(state: WorkerState, config: RunnableConfig) -> Command:
        """调用 LLM 决定下一步工具调用。"""
        from langchain_openai import ChatOpenAI
        from openlearning.config import get_config

        cfg = get_config()
        model = ChatOpenAI(
            model=cfg.llm.models.standard,
            api_key=cfg.llm.api_key,
            base_url=cfg.llm.base_url,
            temperature=0.3,
            max_tokens=cfg.llm.max_tokens,
        )
        model_with_tools = model.bind_tools(tools)

        topic = state.get("topic", "")
        messages: list[BaseMessage] = [
            SystemMessage(content=worker_prompt.format(topic=topic)),
            *state.get("worker_messages", []),
        ]

        try:
            response = await model_with_tools.ainvoke(messages)
            return Command(
                goto="worker_tools",
                update={
                    "worker_messages": [response],
                    "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
                },
            )
        except Exception as e:
            logger.error("Worker LLM 调用失败: %s", e)
            # 失败时直接进入压缩
            error_msg = AIMessage(content=f"执行出错: {e}")
            return Command(
                goto="compress",
                update={"worker_messages": [error_msg]},
            )

    return worker


# ── 工具执行节点 ─────────────────────────────────────────────

def _make_worker_tools_fn(tools: Sequence[BaseTool], max_tool_calls: int = 10):
    """创建 Worker 工具执行节点（闭包，捕获 tools 和 max_tool_calls）。"""

    tools_by_name = {t.name: t for t in tools}

    async def worker_tools(state: WorkerState, config: RunnableConfig) -> Command:
        """执行工具调用，决定继续 Worker 循环或进入压缩。"""
        most_recent = state.get("worker_messages", [])[-1] if state.get("worker_messages") else None

        # 无工具调用 → 直接压缩
        if not most_recent or not hasattr(most_recent, "tool_calls") or not most_recent.tool_calls:
            return Command(goto="compress")

        tool_calls = most_recent.tool_calls

        # 并行执行所有工具调用
        async def _execute_tool(tc: dict) -> str:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})
            tool = tools_by_name.get(tool_name)
            if not tool:
                return f"Error: unknown tool '{tool_name}'"
            try:
                result = await tool.ainvoke(tool_args)
                # 截断过长的工具输出
                result_str = str(result)
                if len(result_str) > 8000:
                    result_str = result_str[:8000] + "\n...(truncated)"
                return result_str
            except Exception as e:
                return f"Error: {type(e).__name__}: {e}"

        observations = await asyncio.gather(
            *[_execute_tool(tc) for tc in tool_calls],
            return_exceptions=True,
        )

        # 构建 ToolMessage
        tool_outputs = []
        for obs, tc in zip(observations, tool_calls):
            content = str(obs) if not isinstance(obs, Exception) else f"Error: {obs}"
            tool_outputs.append(
                ToolMessage(content=content, name=tc["name"], tool_call_id=tc["id"])
            )

        # 退出条件：超迭代
        if state.get("tool_call_iterations", 0) >= max_tool_calls:
            logger.info("Worker 达到工具调用上限 (%s)，进入压缩", max_tool_calls)
            return Command(goto="compress", update={"worker_messages": tool_outputs})

        return Command(goto="worker", update={"worker_messages": tool_outputs})

    return worker_tools


# ── 压缩节点 ────────────────────────────────────────────────

async def _compress(state: WorkerState, config: RunnableConfig) -> dict:
    """将执行历史压缩为结构化摘要，返回给 Supervisor。

    token 超限时渐进截断消息重试。
    """
    from langchain_openai import ChatOpenAI
    from openlearning.config import get_config

    cfg = get_config()
    model = ChatOpenAI(
        model=cfg.llm.models.lite,  # 压缩用轻量模型
        api_key=cfg.llm.api_key,
        base_url=cfg.llm.base_url,
        temperature=0.2,
        max_tokens=cfg.llm.max_tokens,
    )

    topic = state.get("topic", "")
    messages = list(state.get("worker_messages", []))
    messages.append(HumanMessage(content=COMPRESS_HUMAN_PROMPT))

    # token 超限重试（最多 3 次）
    for attempt in range(3):
        try:
            response = await model.ainvoke([
                SystemMessage(content=COMPRESS_SYSTEM_PROMPT),
                *messages,
            ])
            compressed = response.content or "No content"

            # 提取原始笔记
            raw_notes = _extract_raw_notes(state.get("worker_messages", []))

            return {
                "compressed_output": compressed,
                "raw_notes": raw_notes,
            }
        except Exception as e:
            error_str = str(e).lower()
            if "token" in error_str or "length" in error_str or "context" in error_str:
                # token 超限，移除最早的消息重试
                if len(messages) > 3:
                    messages = messages[2:]  # 移除前两条
                    logger.warning("压缩 token 超限，移除早期消息后重试 (attempt %s)", attempt + 1)
                    continue
            logger.error("压缩失败: %s", e)
            break

    return {
        "compressed_output": f"压缩失败: 执行了 {state.get('tool_call_iterations', 0)} 轮工具调用",
        "raw_notes": [],
    }


def _extract_raw_notes(messages: list[BaseMessage]) -> list[str]:
    """从消息历史中提取原始笔记。"""
    notes = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if len(content) > 50:  # 跳过错误消息
                notes.append(content[:500])
    return notes


# ── 子图构建 ────────────────────────────────────────────────

def build_worker_subgraph(
    tools: Sequence[BaseTool],
    worker_prompt: str = WORKER_SYSTEM_PROMPT,
    max_tool_calls: int = 10,
):
    """构建 Worker 子图。

    Args:
        tools: Worker 可使用的工具列表
        worker_prompt: Worker 的系统提示词（需包含 {topic} 占位符）
        max_tool_calls: 最大工具调用次数

    Returns:
        编译后的 Worker 子图
    """
    builder = StateGraph(WorkerState, output=WorkerOutputState)

    builder.add_node("worker", _make_worker_fn(tools, worker_prompt))
    builder.add_node("worker_tools", _make_worker_tools_fn(tools, max_tool_calls))
    builder.add_node("compress", _compress)

    builder.add_edge(START, "worker")
    # worker_tools 内部通过 Command 动态路由回 worker 或 compress
    builder.add_edge("compress", END)

    return builder.compile()
