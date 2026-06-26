"""Shared state definition for the multi-agent system.

All agents read from and write to this TypedDict via LangGraph StateGraph.
Supports both the legacy single-layer architecture and the new three-layer
nested graph architecture (Main Graph → Supervisor Subgraph → Worker Subgraph).
"""

import operator
from typing import Annotated, Any, TypedDict


# ── Reducers ────────────────────────────────────────────────

def override_reducer(current: list, new: Any) -> list:
    """覆盖式 reducer：传入 {"type": "override", "value": [...]} 时替换，否则追加。

    用于需要重置上下文的场景（如 Supervisor 子图初始化时重置消息列表）。
    """
    if isinstance(new, dict) and new.get("type") == "override":
        return new.get("value", [])
    if isinstance(new, list):
        return current + new
    return current + [new]


# ── Legacy Single-Layer State (向后兼容) ────────────────────

class AgentState(TypedDict, total=False):
    """Global shared state for all agents (legacy single-layer architecture)."""

    # ── User Input ───────────────────────────────────────────
    user_request: str  # "我想学 Rust"
    user_profile: dict  # {"level": "intermediate", "lang": ["zh","en"]}

    # ── Memory Output ────────────────────────────────────────
    user_memory: dict  # three-layer memory: project/preference/learning
    avoid_list: Annotated[list[str], operator.add]  # already-recommended URLs

    # ── Planner Output ───────────────────────────────────────
    knowledge_graph: dict  # nodes + edges + dependencies
    search_queries: Annotated[list[str], operator.add]  # generated search keywords
    learning_plan: dict  # full plan with tree + crawl tasks

    # ── Collector Output ─────────────────────────────────────
    raw_resources: Annotated[list[dict], operator.add]  # collected raw resources
    collected_count: int  # total collected so far
    sources_queried: Annotated[list[str], operator.add]  # which sources were queried

    # ── Analyzer Output ──────────────────────────────────────
    analyzed_resources: Annotated[list[dict], operator.add]  # scored + summarized
    avg_quality_score: float
    extracted_concepts: Annotated[list[dict], operator.add]  # knowledge concepts
    concept_relations: Annotated[list[dict], operator.add]  # prerequisite/extends/related

    # ── Evaluation Engine Output ─────────────────────────────
    evaluation: dict  # rule engine results
    iteration: int  # current iteration count

    # ── Reflector Output ─────────────────────────────────────
    reflection: dict  # LLM strategy adjustment suggestions

    # ── Builder Output ───────────────────────────────────────
    learning_system: dict  # generated site path + graph + path

    # ── Supervisor ───────────────────────────────────────────
    supervisor_log: Annotated[list[dict], operator.add]  # decision history

    # ── Flow Control ─────────────────────────────────────────
    current_agent: str  # name of the agent currently executing
    status: str  # running / done / error
    max_iterations: int  # max collection iterations (default 3)
    search_errors: Annotated[list[str], operator.add]  # search error log

    # ── Incremental Update ──────────────────────────────────
    incremental: bool  # True = skip existing resources
    since_days: int  # only search content from the last N days

    # ── Project Context ─────────────────────────────────────
    project_id: str  # 指定项目 ID（更新已有项目时使用）


# ── Three-Layer Nested Graph States ────────────────────────

class AgentInputState(TypedDict, total=False):
    """主图输入状态：仅用户输入字段。"""
    user_request: str
    user_profile: dict
    max_iterations: int
    incremental: bool
    since_days: int
    project_id: str  # 指定项目 ID（更新已有项目时使用）


class SupervisorState(TypedDict, total=False):
    """Supervisor 子图状态：决策循环 + 聚合 Worker 结果。"""
    # Supervisor 决策消息（可覆盖，用于重置上下文）
    supervisor_messages: Annotated[list, override_reducer]
    # 研究简报（来自主图 preprocess）
    research_brief: str
    # 聚合的研究笔记（可覆盖）
    notes: Annotated[list[str], override_reducer]
    # 迭代计数器
    research_iterations: int
    # 原始笔记
    raw_notes: Annotated[list[str], override_reducer]

    # ── 从主图对齐的字段（Subgraph 自动映射）──────────────
    knowledge_graph: dict
    search_queries: Annotated[list[str], operator.add]
    raw_resources: Annotated[list[dict], operator.add]
    analyzed_resources: Annotated[list[dict], operator.add]
    avg_quality_score: float
    extracted_concepts: Annotated[list[dict], operator.add]
    concept_relations: Annotated[list[dict], operator.add]
    evaluation: dict
    iteration: int
    max_iterations: int
    reflection: dict
    status: str
    collected_count: int
    sources_queried: Annotated[list[str], operator.add]
    search_errors: Annotated[list[str], operator.add]


class WorkerState(TypedDict, total=False):
    """Worker 子图状态：ReAct 循环执行具体任务。"""
    # Worker 消息（纯追加，保留完整执行历史供压缩使用）
    worker_messages: Annotated[list, operator.add]
    # 工具调用迭代计数
    tool_call_iterations: int
    # 研究主题
    topic: str
    # 压缩后的输出
    compressed_output: str


class WorkerOutputState(TypedDict, total=False):
    """Worker 子图输出状态：只暴露压缩后的结果给 Supervisor。"""
    compressed_output: str
    raw_notes: Annotated[list[str], override_reducer]
