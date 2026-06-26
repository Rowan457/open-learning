---
name: deep-research-agent-design
description: LangGraph 三层嵌套状态图设计模式 — 主图 → Supervisor 子图 → Worker 子图的分层编排架构
trigger: "deep research|深度研究|agent design|agent设计|三层嵌套|嵌套状态图|supervisor worker|并行研究|nested graph"
---

你是 Agent 架构设计师。当用户需要构建多层嵌套的 LangGraph Agent 系统时，按以下设计原理进行架构设计和代码生成。

---

## 核心思想

将复杂任务拆分为三层状态图，每层各司其职，通过子图嵌套实现分层编排：

```
┌─────────────────────────────────────────────────────┐
│  第一层：主图 (Main Graph)                            │
│  职责：端到端流程控制                                   │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  第二层：Supervisor 子图                        │  │
│  │  职责：任务分解、决策、并行调度                      │  │
│  │                                               │  │
│  │  ┌─────────────┐ ┌─────────────┐              │  │
│  │  │ Worker 子图  │ │ Worker 子图  │  ... × N    │  │
│  │  │ (第三层)     │ │ (第三层)     │              │  │
│  │  │ 职责：执行   │ │ 职责：执行   │              │  │
│  │  └─────────────┘ └─────────────┘              │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**关键原则：每层独立编译、独立状态、通过字段对齐通信。**

---

## 第一层：主图

### 职责

端到端流程：输入 → 前置处理 → 核心执行 → 后置处理 → 输出。

### 状态定义

```python
from langgraph.graph import MessagesState
from typing import Annotated, Optional

def override_reducer(current, new):
    """覆盖式 reducer：传入 {"type": "override", "value": [...]} 时替换，否则追加"""
    if isinstance(new, dict) and new.get("type") == "override":
        return new.get("value", new)
    return operator.add(current, new)

class AgentInputState(MessagesState):
    """输入状态：仅 messages"""
    pass

class AgentState(MessagesState):
    """主图全局状态"""
    supervisor_messages: Annotated[list, override_reducer]  # Supervisor 的消息（可覆盖）
    research_brief: Optional[str]                            # 研究简报
    notes: Annotated[list[str], override_reducer] = []       # 研究笔记（可覆盖）
    final_report: str = ""                                   # 最终报告
```

### 图结构

```python
from langgraph.graph import StateGraph, START, END

builder = StateGraph(AgentState, input=AgentInputState, config_schema=Configuration)

# 前置处理节点
builder.add_node("preprocess", preprocess_fn)

# 核心执行：Supervisor 子图作为节点嵌入
builder.add_node("core_execution", supervisor_subgraph)

# 后置处理节点
builder.add_node("postprocess", postprocess_fn)

# 流程边
builder.add_edge(START, "preprocess")
builder.add_edge("preprocess", "core_execution")
builder.add_edge("core_execution", "postprocess")
builder.add_edge("postprocess", END)

main_graph = builder.compile()
```

### 设计要点

- 主图只关心宏观流程，不关心内部如何执行
- 子图通过 `add_node(name, compiled_subgraph)` 嵌入，LangGraph 自动处理状态映射
- 前置处理负责输入规范化（如澄清、生成研究简报）
- 后置处理负责输出整合（如生成最终报告）

---

## 第二层：Supervisor 子图

### 职责

决策循环：分析任务 → 分解 → 委派给 Worker → 评估结果 → 决定继续或结束。

### 状态定义

```python
class SupervisorState(TypedDict):
    supervisor_messages: Annotated[list, override_reducer]  # 可覆盖，用于重置上下文
    research_brief: str                                      # 来自主图的研究简报
    notes: Annotated[list[str], override_reducer] = []       # 聚合的研究笔记
    research_iterations: int = 0                             # 迭代计数器
    raw_notes: Annotated[list[str], override_reducer] = []   # 原始笔记
```

### 图结构：双节点循环

```python
supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)

supervisor_builder.add_node("supervisor", supervisor_fn)         # 决策节点
supervisor_builder.add_node("supervisor_tools", supervisor_tools_fn)  # 执行节点

supervisor_builder.add_edge(START, "supervisor")
# supervisor_tools 内部通过 Command 动态路由回 supervisor 或 END

supervisor_subgraph = supervisor_builder.compile()
```

### 决策节点

```python
from langgraph.types import Command

async def supervisor(state: SupervisorState, config) -> Command:
    """决策：调用工具 or 结束"""
    cfg = Configuration.from_runnable_config(config)

    # 绑定工具：任务委派 + 完成信号 + 反思
    tools = [ConductResearch, ResearchComplete, think_tool]
    model = configurable_model.bind_tools(tools).with_config(model_config)

    response = await model.ainvoke(state["supervisor_messages"])

    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "research_iterations": state.get("research_iterations", 0) + 1
        }
    )
```

### 执行节点

```python
async def supervisor_tools(state: SupervisorState, config) -> Command:
    """执行工具调用，委派 Worker 或结束"""
    cfg = Configuration.from_runnable_config(config)
    most_recent = state["supervisor_messages"][-1]

    # === 退出条件 ===
    exceeded = state["research_iterations"] > cfg.max_researcher_iterations
    no_calls = not most_recent.tool_calls
    complete = any(t["name"] == "ResearchComplete" for t in most_recent.tool_calls)

    if exceeded or no_calls or complete:
        return Command(goto=END, update={"notes": extract_notes(state)})

    # === 处理 think_tool（反思，不产生外部副作用）===
    think_messages = []
    for t in most_recent.tool_calls:
        if t["name"] == "think_tool":
            think_messages.append(ToolMessage(
                content=f"Reflection recorded: {t['args']['reflection']}",
                name="think_tool",
                tool_call_id=t["id"]
            ))

    # === 处理 ConductResearch（并行委派 Worker）===
    conduct_calls = [t for t in most_recent.tool_calls if t["name"] == "ConductResearch"]

    if conduct_calls:
        allowed = conduct_calls[:cfg.max_concurrent_research_units]
        overflow = conduct_calls[cfg.max_concurrent_research_units:]

        # 并行启动 Worker 子图
        tasks = [
            worker_subgraph.ainvoke({
                "worker_messages": [HumanMessage(content=c["args"]["topic"])],
                "topic": c["args"]["topic"]
            }, config)
            for c in allowed
        ]
        results = await asyncio.gather(*tasks)

        # 构建返回消息
        for result, call in zip(results, allowed):
            think_messages.append(ToolMessage(
                content=result.get("compressed_output", "Error"),
                name=call["name"],
                tool_call_id=call["id"]
            ))

        # 溢出任务返回错误
        for call in overflow:
            think_messages.append(ToolMessage(
                content=f"Error: 超出最大并发数 {cfg.max_concurrent_research_units}",
                name="ConductResearch",
                tool_call_id=call["id"]
            ))

    return Command(
        goto="supervisor",
        update={"supervisor_messages": think_messages}
    )
```

### 设计要点

- Supervisor **只决策不执行**，实际工作交给 Worker
- `asyncio.gather` 实现真正的并行，而非顺序调用
- `max_concurrent_research_units` 限制并发数，防止资源耗尽
- `think_tool` 是伪工具，只记录反思内容，不产生外部副作用
- 退出条件三选一：超迭代 / 无工具调用 / 调用 ResearchComplete

---

## 第三层：Worker 子图

### 职责

执行具体任务：使用工具收集信息 → 压缩结果 → 返回给 Supervisor。

### 状态定义

```python
class WorkerState(TypedDict):
    worker_messages: Annotated[list, operator.add]  # 纯追加，保留完整执行历史
    tool_call_iterations: int = 0
    topic: str
    compressed_output: str

class WorkerOutputState(BaseModel):
    """输出状态：只返回压缩后的结果给 Supervisor"""
    compressed_output: str
    raw_notes: Annotated[list[str], override_reducer] = []
```

### 图结构：双节点循环 + 压缩

```python
worker_builder = StateGraph(WorkerState, output=WorkerOutputState, config_schema=Configuration)

worker_builder.add_node("worker", worker_fn)              # 执行节点
worker_builder.add_node("worker_tools", worker_tools_fn)  # 工具执行
worker_builder.add_node("compress", compress_fn)           # 压缩节点

worker_builder.add_edge(START, "worker")
# worker_tools 内部通过 Command 动态路由回 worker 或 compress
worker_builder.add_edge("compress", END)

worker_subgraph = worker_builder.compile()
```

### 执行节点

```python
async def worker(state: WorkerState, config) -> Command:
    """调用工具执行任务"""
    cfg = Configuration.from_runnable_config(config)
    tools = await get_all_tools(config)  # 搜索工具 + think_tool + MCP 工具

    model = configurable_model.bind_tools(tools).with_config(model_config)
    messages = [SystemMessage(content=worker_prompt)] + state["worker_messages"]
    response = await model.ainvoke(messages)

    return Command(
        goto="worker_tools",
        update={
            "worker_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1
        }
    )
```

### 工具执行节点

```python
async def worker_tools(state: WorkerState, config) -> Command:
    """执行工具调用，决定继续或进入压缩"""
    cfg = Configuration.from_runnable_config(config)
    most_recent = state["worker_messages"][-1]

    # 无工具调用 → 直接压缩
    if not most_recent.tool_calls:
        return Command(goto="compress")

    # 并行执行所有工具
    tools = await get_all_tools(config)
    tools_by_name = {t.name: t for t in tools}

    tasks = [
        execute_tool_safely(tools_by_name[t["name"]], t["args"], config)
        for t in most_recent.tool_calls
    ]
    observations = await asyncio.gather(*tasks)

    tool_outputs = [
        ToolMessage(content=obs, name=t["name"], tool_call_id=t["id"])
        for obs, t in zip(observations, most_recent.tool_calls)
    ]

    # 退出条件：超迭代 或 ResearchComplete
    exceeded = state["tool_call_iterations"] >= cfg.max_tool_calls
    complete = any(t["name"] == "ResearchComplete" for t in most_recent.tool_calls)

    if exceeded or complete:
        return Command(goto="compress", update={"worker_messages": tool_outputs})

    return Command(goto="worker", update={"worker_messages": tool_outputs})
```

### 压缩节点

```python
async def compress(state: WorkerState, config):
    """将执行历史压缩为结构化摘要，返回给 Supervisor"""
    cfg = Configuration.from_runnable_config(config)
    messages = state["worker_messages"]
    messages.append(HumanMessage(content="请清理上述发现，保留所有相关信息但去除重复。"))

    model = configurable_model.with_config(compression_model_config)

    # token 超限重试
    for attempt in range(3):
        try:
            response = await model.ainvoke([
                SystemMessage(content=compress_prompt),
                *messages
            ])
            return {
                "compressed_output": response.content,
                "raw_notes": [extract_raw_notes(messages)]
            }
        except Exception as e:
            if is_token_limit_exceeded(e):
                messages = remove_up_to_last_ai_message(messages)
                continue

    return {"compressed_output": "Error: Maximum retries exceeded", "raw_notes": []}
```

### 设计要点

- `output=WorkerOutputState` 限制 Worker 只返回压缩后的结果，而非全部历史
- `worker_messages` 用 `operator.add`（纯追加），保留完整执行上下文供压缩使用
- 压缩节点是 Worker 的出口，确保返回给 Supervisor 的是精简信息
- token 超限时渐进截断消息重试

---

## 状态流转全景

```
用户输入
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ 主图: AgentState                                        │
│                                                         │
│  preprocess → [research_brief 生成]                     │
│       │                                                 │
│       ▼                                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Supervisor 子图: SupervisorState                 │   │
│  │                                                  │   │
│  │  supervisor → [决策: 分解任务]                    │   │
│  │       │                                         │   │
│  │       ▼                                         │   │
│  │  supervisor_tools → [并行调度 Worker]            │   │
│  │       │                                         │   │
│  │       ├── think_tool → 记录反思                  │   │
│  │       ├── ConductResearch × N → 并行启动 Worker  │   │
│  │       │       │                                 │   │
│  │       │       ▼                                 │   │
│  │       │  ┌──────────────────────────────────┐   │   │
│  │       │  │ Worker 子图: WorkerState          │   │   │
│  │       │  │                                  │   │   │
│  │       │  │  worker → [调用搜索工具]          │   │   │
│  │       │  │    ↕ (ReAct 循环)                │   │   │
│  │       │  │  worker_tools → [执行工具]        │   │   │
│  │       │  │    │                             │   │   │
│  │       │  │    ▼                             │   │   │
│  │       │  │  compress → [压缩结果]           │   │   │
│  │       │  │    │                             │   │   │
│  │       │  │    ▼                             │   │   │
│  │       │  │  输出: compressed_output         │   │   │
│  │       │  └──────────────────────────────────┘   │   │
│  │       │                                         │   │
│  │       ▼                                         │   │
│  │  回到 supervisor → [评估结果，决定继续或结束]     │   │
│  │       │                                         │   │
│  │       ▼ (ResearchComplete 或超迭代)              │   │
│  │  输出: notes + research_brief                   │   │
│  └──────────────────────────────────────────────────┘   │
│       │                                                 │
│       ▼                                                 │
│  postprocess → [生成最终报告]                           │
│       │                                                 │
│       ▼                                                 │
│  输出: final_report                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 层间通信规则

| 维度 | 主图 ↔ Supervisor | Supervisor ↔ Worker |
|------|-------------------|---------------------|
| **状态映射** | 主图的 `supervisor_messages` 对应 Supervisor 的输入 | Supervisor 的 `ConductResearch.args.topic` 对应 Worker 的输入 |
| **返回值** | Supervisor 返回 `notes` 和 `research_brief` | Worker 返回 `WorkerOutputState`（仅压缩结果） |
| **信息过滤** | Supervisor 不把全部消息返回给主图 | Worker 不把全部执行历史返回给 Supervisor |
| **并发控制** | 无（主图串行） | `max_concurrent_research_units` 限制并行 Worker 数 |

### 关键：output 状态过滤

```python
# Worker 子图定义时指定 output
worker_builder = StateGraph(
    WorkerState,              # 完整内部状态
    output=WorkerOutputState, # 只暴露这个子集给 Supervisor
    config_schema=Configuration
)
```

这确保 Supervisor 只收到 `compressed_output`，而非 Worker 的全部 `worker_messages`。

---

## override_reducer 的作用

默认的 `operator.add` reducer 只会追加。但在某些场景需要**覆盖**：

```python
# 场景：主图初始化 Supervisor 时，需要重置 supervisor_messages
return Command(
    goto="supervisor",
    update={
        "supervisor_messages": {
            "type": "override",  # 触发覆盖
            "value": [
                SystemMessage(content=supervisor_prompt),
                HumanMessage(content=research_brief)
            ]
        }
    }
)
```

没有 `override_reducer`，新消息会追加到旧消息后面，导致 Supervisor 看到过时的上下文。

---

## 快速启动检查清单

- [ ] 定义三层状态：`AgentState` / `SupervisorState` / `WorkerState` + `WorkerOutputState`
- [ ] 实现 `override_reducer` 处理状态覆盖需求
- [ ] 从底层开始编译：Worker 子图 → Supervisor 子图 → 主图
- [ ] Supervisor 用 `asyncio.gather` 并行调度 Worker
- [ ] Worker 用 `output=WorkerOutputState` 过滤返回值
- [ ] 压缩节点作为 Worker 的必经出口
- [ ] 所有 LLM 调用包裹 token 超限重试
