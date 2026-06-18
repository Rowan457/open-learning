# OpenLearning — 智能学习资料收集 Agent

## Project Specs v1.0

---

## 1. 项目愿景

构建一个 **AI 驱动的个人学习信息系统**，用户只需输入一个学习主题（如"机器学习"、"Rust 编程"、"量子计算入门"），系统便能：

1. **自动从全网搜集** 相关的高质量学习资源
2. **智能筛选与排序** 基于质量、时效性、难度等维度
3. **结构化整理** 生成清晰的知识体系和学习路径
4. **生成静态课程网站** 可本地预览或部署上线
5. **持续追踪更新** 定期检查资源变化，推送新内容

> **一句话定位**：告诉它你想学什么，它帮你把整个互联网变成一本结构化的教科书。

---

## 2. 核心用户场景

| 场景 | 用户输入 | 系统输出 |
|------|----------|----------|
| 快速入门 | "我想学 Rust" | 一份从零到实战的 Rust 学习路径 + 资源网站 |
| 深度研究 | "Transformer 架构的演进" | 论文、博客、视频的时序梳理 + 关键技术对比 |
| 技能补强 | "我已会 Python，想补系统设计" | 定制化的进阶学习路径，跳过基础 |
| 持续追踪 | "关注 LLM Agent 领域的最新进展" | 每周自动更新的资源看板 |

---

## 3. 系统架构

### 3.1 LangGraph Multi-Agent 架构

参考 [LangChain Open Deep Research](https://github.com/langchain-ai/open_deep_research) 的 Multi-Agent 模式，采用 **Supervisor + Sub-Agent** 架构，每个 Agent 是一个 LangGraph 子图（Subgraph），由 Supervisor 统一编排。

```
                         用户输入
                     "我想学 Rust 编程"
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Supervisor Agent (主图)                           │
│                    ┌─────────────────────┐                          │
│                    │  LangGraph StateGraph│                         │
│                    │  状态驱动 · 条件路由  │                         │
│                    └──────────┬──────────┘                          │
│                               │                                     │
│  ┌─────────┬─────────┬────────┼────────┬──────────┬──────────┐     │
│  ▼         ▼         ▼        ▼        ▼          ▼          ▼     │
│ ┌───────┐┌────────┐┌───────┐┌──────┐┌────────┐┌────────┐┌───────┐ │
│ │Memory ││Planner ││Collect││Analyz││Evaluat.││Reflect.││Builder│ │
│ │ Agent ││ Agent  ││Agent  ││Agent ││Engine  ││ Agent  ││ Agent │ │
│ │       ││        ││       ││      ││(规则)  ││        ││       │ │
│ │记忆查询││知识图谱 ││多源采集││知识提取││质量/覆盖││策略反思 ││学习系统│ │
│ │偏好学习││搜索规划 ││去重   ││关系发现││达标判定 ││缺口分析 ││图谱渲染│ │
│ └───────┘└────────┘└───────┘└──────┘└────────┘└────────┘└───────┘ │
│       │           │           │           │           │            │
│       └───────────┴───────────┴───────────┴───────────┘            │
│                           │                                         │
│                    ┌──────┴──────┐                                  │
│                    │ Shared State │  ← TypedDict 全局状态           │
│                    │ (状态图节点)  │     所有 Agent 共享读写          │
│                    └──────┬──────┘                                  │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Skill 层                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ search   │ │ fetch    │ │ analyze  │ │ persist  │ │ render  │ │
│  │ Skill    │ │ Skill    │ │ Skill    │ │ Skill    │ │ Skill   │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ │
└───────┼────────────┼────────────┼────────────┼────────────┼───────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ Google   │ │ httpx +  │ │ LLM API  │ │ SQLite   │ │ Jinja2   │
  │ arXiv   │ │trafilatur│ │(多模型)  │ │ 文件系统 │ │ 模板引擎 │
  │ YouTube │ │ e        │ │          │ │          │ │          │
  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
                            │
                            ▼
                      ┌──────────┐
                      │ LangSmith│
                      │ (可观测) │
                      └──────────┘
```

### 3.2 核心设计模式

| 模式 | 来源 | 在 OpenLearning 中的应用 |
|------|------|--------------------------|
| **StateGraph** | LangGraph | 全局状态驱动，Agent 通过读写共享状态协作 |
| **LLM Supervisor** | LangGraph | Supervisor 是 LLM Agent，推理决策而非查表跳转 |
| **Sub-Agent 子图** | LangGraph | 每个 Agent 是独立子图，可独立测试 |
| **Reflection 循环** | open_deep_research | Reflector + Evaluation Engine 双重审查 |
| **知识图谱** | 自研 | Analyzer 提取概念+关系，Builder 渲染为可交互图谱 |
| **Memory 持久化** | MemGPT 启发 | Memory Agent 学习用户偏好，避免重复推荐 |
| **规则引擎** | 自研 | Evaluation Engine 用规则（非 LLM）做质量/覆盖判定，降低成本 |
| **Skill 模块化** | LangChain Tools | 所有外部能力封装为独立 Skill |

### 3.3 Graph 流程

```
START
  │
  ▼
┌─────────────┐
│   Memory    │  ← 查询用户历史、偏好、已学内容
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Planner   │  ← 分析需求，生成知识图谱 + 采集计划
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Collector  │  ← 按计划并行采集（可多轮）
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Analyzer   │  ← 内容提取 + 知识提取 + 关系发现
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Evaluation  │  ← 规则引擎：质量/覆盖/多样性检查
│  Engine     │     不达标 → 返回 Collector 补充
└──────┬──────┘
       │ (通过)
       ▼
┌─────────────┐
│  Reflector  │  ← LLM 反思：策略调整、深度优化建议
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Builder   │  ← 生成知识图谱学习系统（非资源列表）
└──────┬──────┘
       │
       ▼
      END
```



## 4. Sub-Agent 详细设计

> 基于 LangGraph StateGraph 的五个 Sub-Agent，每个是独立子图，由 Supervisor 编排。

### 4.A 功能 Agent

> 直接面向用户的核心功能——输入学习需求，输出结构化资源和课程网站。

### 4.0 Supervisor Agent 与共享状态

#### Supervisor（LLM 决策者）

Supervisor **不是状态机**，而是一个 LLM Agent。它观察全局状态，**推理**下一步应该做什么，而不是查表跳转。

```python
from langgraph.prebuilt import create_react_agent

# Supervisor 是一个 LLM Agent，拥有所有 Sub-Agent 作为 tools
supervisor = create_react_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[
        planner_agent,      # "分析需求，生成知识树"
        collector_agent,    # "采集资源"
        analyzer_agent,     # "分析内容，提取知识"
        evaluator_engine,   # "评估质量（规则引擎）"
        reflector_agent,    # "反思缺口，决定是否补充"
        memory_agent,       # "查询/更新用户记忆"
        builder_agent,      # "生成学习系统"
    ],
    state_schema=AgentState,
    prompt="""你是 OpenLearning 的 Supervisor。
    观察当前状态，推理下一步应该调用哪个 Agent。
    不要按固定顺序执行，根据实际情况决策。
    如果资源质量不够，主动要求补充采集。
    如果用户已有相关项目记忆，先查询 Memory。
    """,
)
```

#### Shared State（全局状态）

```python
class AgentState(TypedDict):
    """所有 Agent 共享的全局状态"""
    # 用户输入
    user_request: str                    # "我想学 Rust"
    user_profile: dict                   # {"level": "intermediate", "lang": ["zh","en"]}

    # Memory 输出
    user_memory: dict                    # 历史项目、偏好、已学内容
    avoid_list: list[str]                # 已推荐过的资源 URL（去重用）

    # Planner 输出
    knowledge_graph: dict                # 知识图谱（节点+边+依赖关系）
    search_queries: list[str]            # 生成的搜索关键词

    # Collector 输出
    raw_resources: list[dict]            # 采集到的原始资源
    collected_count: int                 # 已采集数量

    # Analyzer 输出
    analyzed_resources: list[dict]       # 评分 + 摘要 + 知识提取后的资源
    avg_quality_score: float             # 平均质量分
    extracted_concepts: list[dict]       # 提取的知识概念
    concept_relations: list[dict]        # 概念间的关系（前置/进阶/相关）

    # Evaluation Engine 输出
    evaluation: dict                     # 规则引擎评估结果
    iteration: int                       # 当前迭代轮次

    # Reflector 输出
    reflection: dict                     # LLM 反思：策略调整建议

    # Builder 输出
    learning_system: dict                # 生成的学习系统（知识图谱+路径+站点）

    # 流程控制
    current_agent: str                   # 当前执行的 Agent 名
    status: str                          # running / done / error
```

#### 与状态机的区别

| 维度 | 状态机（旧） | LLM Supervisor（新） |
|------|-------------|---------------------|
| **路由方式** | `transitions[current]` 查表 | LLM 观察状态，推理决策 |
| **灵活性** | 固定顺序 planner→collector→... | 可跳过、可重复、可并行 |
| **异常处理** | 无法处理意外情况 | LLM 可自主调整策略 |
| **人机交互** | 不支持 | 可在关键节点请求人工确认 |
| **示例** | collector→analyzer（固定） | "Memory 已有类似项目，先查 Memory 再决定是否重新采集" |

### 4.1 Planner Agent（学习规划子图）

**职责**：将用户的自然语言学习需求，拆解为结构化的知识树和采集计划。

```python
class PlannerState(TypedDict):
    user_request: str
    user_profile: dict
    knowledge_tree: dict         # 知识树
    search_queries: list[str]    # 搜索关键词矩阵
    crawl_plan: list[dict]       # 采集任务列表

def planner_agent(state: AgentState) -> dict:
    """Planner 子图：需求分析 → 知识树展开 → 搜索词生成"""
    # 1. LLM 分析用户需求
    analysis = llm.analyze(state["user_request"], state["user_profile"])

    # 2. 展开知识树
    tree = llm.expand_knowledge_tree(analysis["topic"], analysis["subtopics"])

    # 3. 生成搜索关键词矩阵
    queries = generate_search_queries(tree, analysis["resource_types"])

    return {
        "learning_plan": {"tree": tree, "crawl_plan": queries},
        "search_queries": queries,
        "current_agent": "planner",
    }
```

**输出写入状态**：`learning_plan`, `search_queries`

**关键能力**：
- 知识图谱展开：从主题自动推导前置知识和进阶方向
- 用户画像适配：根据已有基础调整深度
- 多语言策略：中英文资源混合搜索

### 4.2 Collector Agent（资源采集子图）

**职责**：根据 Planner 生成的搜索关键词，并行调用多个数据源采集原始资源。

```python
# Skills 通过 LangChain Tool 注入，每个 Skill 模块导出一组 tools
# 使用时直接调用 tool.ainvoke()

def collector_agent(state: AgentState) -> dict:
    """Collector 子图：通过 Skill 多源并行采集 → 去重 → 持久化"""
    queries = state["search_queries"]

    # 1. 并行采集（调用 search Skill）
    tasks = []
    for query in queries:
        tasks.append(web_search.ainvoke({"query": query, "max_results": 20}))
        tasks.append(arxiv_search.ainvoke({"query": query, "max_results": 10}))
        tasks.append(youtube_search.ainvoke({"query": query, "max_results": 10}))
        tasks.append(github_search.ainvoke({"query": query}))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 2. 去重 + 标准化
    all_resources = flatten(results)
    deduplicated = deduplicate(all_resources, key="url")

    # 3. 持久化（调用 persist Skill）
    for res in deduplicated:
        await save_resource.ainvoke({"resource": res})

    # 4. 更新状态
    prev_count = state.get("collected_count", 0)
    return {
        "raw_resources": deduplicated,
        "collected_count": prev_count + len(deduplicated),
        "sources_queried": ["google", "arxiv", "youtube", "github"],
        "current_agent": "collector",
    }
```

**输出写入状态**：`raw_resources`, `collected_count`, `sources_queried`

#### 数据源矩阵

| 源类型 | 具体来源 | 采集方式 | 资源类型 |
|--------|----------|----------|----------|
| 搜索引擎 | Google, Bing, DuckDuckGo | API / SerpAPI | 网页、博客 |
| 学术 | arXiv, Semantic Scholar, Google Scholar | API | 论文、预印本 |
| 视频 | YouTube, Bilibili | API / 爬虫 | 视频教程 |
| 代码 | GitHub, GitLab | API | 项目、示例代码 |
| 课程 | Coursera, edX, Udemy | 网页抓取 | 在线课程 |
| 社区 | Reddit, HackerNews, 知乎, V2EX | API / RSS | 讨论、推荐 |
| 文档 | MDN, DevDocs, ReadTheDocs | 爬虫 | 官方文档 |
| RSS/Atom | 各大技术博客 | RSS 解析 | 博客文章 |

#### 采集策略

- **广度优先**：先铺面，每个子主题至少覆盖 3 个源
- **深度追踪**：对高价值资源（如权威博客）递归抓取关联内容
- **限流合规**：遵守 robots.txt，请求间隔 1-3 秒随机延迟
- **增量更新**：记录上次采集时间，仅抓取新增/变更内容
- **Reflector 驱动重采**：当 Reflector 标记资源缺口时，定向补充采集

### 4.3 Analyzer Agent（知识提取子图）

**职责**：对采集到的原始资源进行内容提取、知识提取、关系发现和质量标注。**不只是评分和摘要，而是从资源中提取结构化知识，构建知识图谱的节点和边。**

```python
def analyzer_agent(state: AgentState) -> dict:
    """Analyzer 子图：内容提取 → 知识提取 → 关系发现 → 标注"""
    resources = state["raw_resources"]
    knowledge_graph = state.get("knowledge_graph", {})
    analyzed = []
    all_concepts = []
    all_relations = []

    for resource in resources:
        # 1. 内容提取（调用 fetch Skill）
        content = await fetch_page.ainvoke({"url": resource["url"]})

        # 2. 知识提取（LLM）— 从内容中提取概念、定义、原理
        knowledge = await extract_knowledge.ainvoke({
            "content": content,
            "existing_concepts": [c["name"] for c in all_concepts],
        })

        # 3. 关系发现（LLM）— 发现概念间的前置/进阶/相关关系
        relations = await discover_relations.ainvoke({
            "new_concepts": knowledge["concepts"],
            "existing_graph": knowledge_graph,
        })

        # 4. 智能标注
        tags = await tag.ainvoke({"content": content})

        all_concepts.extend(knowledge["concepts"])
        all_relations.extend(relations)

        analyzed.append({
            **resource,
            "content_preview": content[:500],
            "knowledge": knowledge,           # 提取的知识点
            "tags": tags,
        })

    # 5. 合并到知识图谱
    updated_graph = merge_into_graph(knowledge_graph, all_concepts, all_relations)

    # 6. 持久化
    for res in analyzed:
        await save_resource.ainvoke({"resource": res})

    return {
        "analyzed_resources": analyzed,
        "extracted_concepts": all_concepts,
        "concept_relations": all_relations,
        "knowledge_graph": updated_graph,
        "current_agent": "analyzer",
    }
```

**输出写入状态**：`analyzed_resources`, `extracted_concepts`, `concept_relations`, `knowledge_graph`

#### 知识提取流水线

```
原始资源 (URL + 正文)
         │
         ▼
  ┌──────────────┐
  │ 内容提取      │  ← 正文 / 代码块 / 元数据
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ 知识提取      │  ← LLM 从内容中提取：
  │ (LLM)        │     • 概念 (concept): 名称 + 定义 + 示例
  └──────┬───────┘     • 原理 (principle): 核心规则/公式/模式
         │              • 技术 (technology): 工具/框架/库
         ▼              • 最佳实践 (best_practice)
  ┌──────────────┐
  │ 关系发现      │  ← LLM 发现概念间的关系：
  │ (LLM)        │     • prerequisite(A, B): 学 B 前要先学 A
  └──────┬───────┘     • extends(A, B): A 是 B 的进阶
         │              • related(A, B): A 和 B 相关
         ▼              • contradicts(A, B): A 和 B 有冲突
  ┌──────────────┐
  │ 图谱合并      │  ← 新概念合并到已有知识图谱
  │              │     去重、更新关系、计算节点权重
  └──────────────┘
```

#### 知识图谱数据结构

```python
# 知识图谱节点
{
    "id": "rust_ownership",
    "name": "所有权 (Ownership)",
    "type": "concept",                    # concept / principle / technology / practice
    "definition": "Rust 的内存管理模型...",
    "examples": ["let s = String::from(\"hello\")"],
    "resources": ["url1", "url3"],        # 来源资源
    "difficulty": "intermediate",
    "importance": 0.9,                    # 在图谱中的重要度
}

# 知识图谱边
{
    "from": "rust_borrowing",
    "to": "rust_ownership",
    "type": "prerequisite",               # prerequisite / extends / related
    "weight": 0.95,                       # 关系强度
    "reason": "借用是所有权的延伸，必须先理解所有权",
}
```

### 4.4 Memory Agent（用户记忆子图）

**职责**：学习用户偏好、记录历史项目、避免重复推荐。是 Agent 的**长期记忆**。

```python
def memory_agent(state: AgentState) -> dict:
    """Memory 子图：查询历史 → 学习偏好 → 过滤重复"""
    user_id = state["user_profile"].get("user_id")

    # 1. 查询历史项目
    history = await query_db.ainvoke({
        "sql": "SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC LIMIT 5",
        "params": [user_id],
    })

    # 2. 查询用户偏好（从历史行为学习）
    preferences = await learn_preferences.ainvoke({"history": history})

    # 3. 获取已推荐资源列表（去重用）
    avoid_list = await query_db.ainvoke({
        "sql": "SELECT url FROM resources WHERE project_id IN (SELECT id FROM projects WHERE user_id = ?)",
        "params": [user_id],
    })

    # 4. 检查是否有类似项目（避免重复劳动）
    similar_project = find_similar_project(history, state["user_request"])

    return {
        "user_memory": {
            "history": history,
            "preferences": preferences,
            "similar_project": similar_project,
        },
        "avoid_list": [r["url"] for r in avoid_list],
        "current_agent": "memory",
    }
```

**输出写入状态**：`user_memory`, `avoid_list`

#### 记忆维度

| 维度 | 存储内容 | 用途 |
|------|----------|------|
| **历史项目** | 主题、资源数、质量分、完成度 | 避免重复采集，推荐进阶内容 |
| **用户偏好** | 偏好资源类型、语言、难度、学习风格 | 个性化排序和筛选 |
| **已学内容** | 已掌握的概念、已完成的资源 | 跳过基础，推荐进阶 |
| **反馈记录** | 用户对资源的评分、收藏、跳过行为 | 优化推荐算法 |

---

### 4.5 Evaluation Engine（规则引擎）

**职责**：用**规则**（非 LLM）做质量检查、覆盖度检查、多样性检查。成本低、速度快、可解释。

```python
def evaluator_engine(state: AgentState) -> dict:
    """Evaluation Engine：规则驱动的质量/覆盖/多样性检查"""
    resources = state["analyzed_resources"]
    graph = state["knowledge_graph"]
    iteration = state.get("iteration", 0)

    # 1. 质量检查（规则）
    quality = rule_check_quality(resources, min_avg=6.0, min_single=3.0)

    # 2. 覆盖检查（对比知识图谱节点 vs 已有资源）
    coverage = rule_check_coverage(graph, resources)

    # 3. 多样性检查（规则）
    diversity = rule_check_diversity(resources, min_types=3)

    # 4. 时效性检查（规则）
    freshness = rule_check_freshness(resources, min_recent_ratio=0.3)

    # 5. 综合判定
    all_passed = all([quality["pass"], coverage["pass"], diversity["pass"], freshness["pass"]])
    forced_pass = iteration >= state.get("max_iterations", 3)

    return {
        "evaluation": {
            "pass": all_passed or forced_pass,
            "quality": quality,
            "coverage": coverage,
            "diversity": diversity,
            "freshness": freshness,
        },
        "iteration": iteration + 1,
        "current_agent": "evaluator",
    }
```

**输出写入状态**：`evaluation`, `iteration`

#### 规则引擎检查项

| 检查项 | 规则 | 不达标动作 |
|--------|------|-----------|
| **质量** | 平均分 ≥ 6.0，单个 ≥ 3.0 | 淘汰低分资源，标记补充 |
| **覆盖** | 知识图谱每个核心节点 ≥ 1 个资源 | 生成补充搜索词 |
| **多样性** | 资源类型 ≥ 3 种 | 针对缺失类型定向搜索 |
| **时效** | 最近 1 年资源占比 ≥ 30% | 增加时间限定搜索 |
| **难度** | 三个难度级别均有覆盖 | 针对缺失难度补充 |

---

### 4.6 Tool Router（工具路由）

**职责**：根据当前任务上下文，选择最合适的 Skill/Tool 调用。避免 Agent 硬编码工具选择。

```python
def tool_router_agent(state: AgentState) -> dict:
    """Tool Router：根据任务上下文选择最佳工具组合"""
    task = state.get("current_task", "")
    context = state.get("task_context", {})

    # LLM 推理：当前任务应该调用哪些工具
    tool_plan = await llm.plan_tool_usage(
        task=task,
        available_tools=get_all_tools(),
        context=context,
    )

    # tool_plan 示例:
    # {
    #   "tools": ["web_search", "arxiv_search"],
    #   "params": [
    #     {"query": "Rust ownership tutorial", "max_results": 20},
    #     {"query": "Rust ownership paper", "max_results": 5},
    #   ],
    #   "reason": "用户想学所有权，需要教程+论文两种资源"
    # }

    return {
        "tool_plan": tool_plan,
        "current_agent": "tool_router",
    }
```

**使用场景**：
- Supervisor 决定 "需要补充采集" → Tool Router 选择具体搜索源和关键词
- 用户请求 "找 Rust 视频教程" → Tool Router 选择 youtube_search + bilibili_search
- 需要 "深入分析这个论文" → Tool Router 选择 fetch_page + parse_pdf + extract_knowledge

---

### 4.7 Reflector Agent（策略反思子图）

**职责**：基于 Evaluation Engine 的结果，用 LLM 进行**策略层面的反思**——不是重复规则检查，而是思考"为什么不够好"和"应该怎么调整"。

```python
def reflector_agent(state: AgentState) -> dict:
    """Reflector 子图：LLM 策略反思（非规则检查）"""
    evaluation = state["evaluation"]
    graph = state["knowledge_graph"]
    memory = state.get("user_memory", {})

    # LLM 反思：基于评估结果，生成策略调整建议
    reflection = await llm.reflect(
        evaluation=evaluation,
        knowledge_graph=graph,
        user_memory=memory,
        prompt="""分析评估结果，回答：
        1. 哪些知识节点资源不足？为什么？（搜索词不够精准？源选择不对？）
        2. 质量低的资源有什么共同特征？如何避免？
        3. 用户已有哪些知识？应该跳过什么、深入什么？
        4. 下一轮采集应该调整什么策略？
        """,
    )

    return {
        "reflection": reflection,
        "current_agent": "reflector",
    }
```

**输出写入状态**：`reflection`

#### Reflector vs Evaluation Engine

| 维度 | Evaluation Engine | Reflector |
|------|------------------|-----------|
| **方法** | 规则引擎（if/else） | LLM 推理 |
| **成本** | 零 token 消耗 | 消耗 token |
| **速度** | 毫秒级 | 秒级 |
| **能力** | 质量/覆盖/多样性/时效 | 策略调整/根因分析/个性化建议 |
| **输出** | pass/fail + 数值 | 文字建议 + 调整方案 |

---

### 4.8 Builder Agent（学习系统生成子图）

**职责**：不是生成"资源列表网站"，而是生成**知识图谱驱动的学习系统**——包含可交互的知识图谱、个性化学习路径、进度追踪。

```python
def builder_agent(state: AgentState) -> dict:
    """Builder 子图：知识图谱 → 学习路径 → 学习系统"""
    graph = state["knowledge_graph"]
    resources = state["analyzed_resources"]
    memory = state.get("user_memory", {})

    # 1. 生成个性化学习路径（知识图谱拓扑排序 + 用户已有知识）
    learning_path = generate_learning_path(
        graph=graph,
        user_knowledge=memory.get("learned_concepts", []),
        preferences=memory.get("preferences", {}),
    )

    # 2. 为每个知识点匹配最佳资源
    knowledge_resources = match_resources_to_concepts(graph, resources)

    # 3. 生成学习系统站点
    site_path = await build_learning_system.ainvoke({
        "knowledge_graph": graph,
        "learning_path": learning_path,
        "knowledge_resources": knowledge_resources,
        "output_dir": "./output/",
    })

    # 4. 保存项目（供 Memory Agent 未来使用）
    await save_project.ainvoke({"title": state["user_request"], "knowledge_graph": graph})

    return {
        "learning_system": {"site_path": site_path, "knowledge_graph": graph, "learning_path": learning_path},
        "current_agent": "builder",
        "status": "done",
    }
```

**输出写入状态**：`learning_system`, `status`

#### 生成的学习系统结构

```
output/
├── index.html                    # 首页：知识图谱全景
├── graph.html                    # 可交互知识图谱 (D3.js / Cytoscape.js)
│                                 #   节点=知识点，边=依赖关系
│                                 #   颜色=掌握程度，点击→学习页
├── learning-path.html            # 个性化学习路径（拓扑排序+跳过已掌握）
├── knowledge/
│   ├── ownership.html            # 每个知识点独立页面
│   ├── borrowing.html            #   定义/原理/示例/关联/资源
│   └── ...
├── progress.html                 # 学习进度追踪 (localStorage)
├── search.html                   # 全文搜索
└── data/
    ├── knowledge-graph.json      # 知识图谱数据
    ├── learning-path.json        # 学习路径
    └── resources.json            # 资源数据
```

#### 学习系统特性

| 特性 | 实现方案 | 价值 |
|------|----------|------|
| **知识图谱** | D3.js / Cytoscape.js | 全局视角理解知识结构 |
| **学习路径** | 拓扑排序 + 用户画像 | 个性化，跳过已掌握 |
| **知识点页** | 每个概念独立页面 | 聚焦学习，不被资源淹没 |
| **进度追踪** | localStorage | 可视化学习进度 |
| **资源匹配** | 概念↔资源关联 | 按需学习 |

## 5. Agent 基础设施 (`4.B`)

> 运行时支撑层——不直接面向用户，但决定了 Agent 的效率、质量和可维护性。

### 5.1 上下文压缩 (Context Compression)

**核心问题**：单个 Phase 内，Agent 会进行大量探索（搜索、阅读、分析），上下文快速膨胀。仅靠 Phase 边界的 git checkpoint 不够——Phase 内部也需要压缩。

#### 压缩策略分层

```
原始上下文 (对话 + 工具结果 + 代码)
    │ 70% max_tokens
    ▼
L1 滑动窗口: 最近 5 轮完整，早期降级为摘要
    │ 85%
    ▼
L2 渐进式摘要: 工具结果→仅结论，代码→仅签名
    │ 95%
    ▼
L3 决策日志: 整段历史→结构化「做了什么/为什么/结果」
    │ Phase 边界
    ▼
完全清除 → 从 git log 恢复
```

#### 各层压缩规则

| 层级 | 内容类型 | 保留策略 |
|------|----------|----------|
| **L1** | 最近 5 轮对话 | 完整保留 |
| | 更早对话 | 一句话摘要 |
| | 系统提示 / 当前任务 | 始终保留 |
| **L2** | 搜索结果 | top-5 标题+URL+摘要，丢弃其余 |
| | 网页抓取 | LLM 关键段落，丢弃原文 |
| | 代码文件 | 函数签名+类定义，丢弃函数体 |
| | LLM 分析 | 结论+评分，丢弃推理过程 |
| **L3** | 全部历史 | 结构化决策日志（已完成/当前状态/关键发现/下一步） |

#### 压缩触发机制

```python
class ContextManager:
    MAX_TOKENS = 128_000          # 模型上下文窗口
    WARN_THRESHOLD = 0.70         # 70% 时开始第一层压缩
    COMPRESS_THRESHOLD = 0.85     # 85% 时触发第二层压缩
    CRITICAL_THRESHOLD = 0.95     # 95% 时触发第三层压缩

    def check_and_compress(self, context):
        usage = self.estimate_tokens(context) / self.MAX_TOKENS

        if usage > self.CRITICAL_THRESHOLD:
            return self.compress_level_3(context)  # 决策日志
        elif usage > self.COMPRESS_THRESHOLD:
            return self.compress_level_2(context)  # 工具输出压缩
        elif usage > self.WARN_THRESHOLD:
            return self.compress_level_1(context)  # 滑动窗口
        return context
```

#### 数据库辅助压缩

并非所有数据都需要留在上下文中。频繁使用 SQLite 作为外部记忆：

```
上下文中的数据          →    SQLite 中的数据
─────────────────────────────────────────────
搜索结果列表 (50条)     →    仅保留 top-5 摘要，其余写入 DB
网页全文 (10KB/篇)      →    仅保留关键段落摘要，全文在 DB
质量评分详细理由        →    仅保留分数，理由写入 DB
采集的原始元数据        →    全部写入 DB，上下文中仅保留计数
```

**Agent 需要时可以随时查询 DB**，而不是把所有数据都塞进上下文。

---

### 5.2 Skill 系统

**核心理念**：将 Agent 的外部能力封装为独立的 Skill 模块。每个 Skill 是一个 LangChain Tool，有明确的输入/输出 Schema，由 Agent 通过 `tool.invoke()` 调用。

#### Skill 架构

Agent 通过 `bind_tools()` 绑定 Skill，Skill 通过 LangChain `@tool` 装饰器定义。详见 §3.1 架构图。

```
Agent (bind_tools)
    │
    ├── search Skill   → web_search / arxiv_search / youtube_search / github_search
    ├── fetch Skill    → fetch_page / extract / parse_pdf
    ├── analyze Skill  → score / summarize / tag / extract_knowledge / discover_relations / compare
    ├── persist Skill  → save_resource / query_db / export
    ├── render Skill   → build_learning_system / preview / deploy
    └── git Skill      → checkpoint / log / diff
```

#### Skill 清单

| Skill | Tool 名称 | 描述 | 输入 | 输出 |
|-------|-----------|------|------|------|
| **search** | `web_search` | Google/Bing 搜索 | `query`, `max_results` | 结果列表 |
| | `arxiv_search` | 学术论文搜索 | `query`, `max_results` | 论文列表 |
| | `youtube_search` | 视频搜索 | `query`, `max_results` | 视频列表 |
| | `github_search` | 代码仓库搜索 | `query`, `language` | 仓库列表 |
| **fetch** | `fetch_page` | 网页内容提取 | `url` | 正文 + 元数据 |
| | `extract` | 结构化提取 | `content`, `schema` | 结构化数据 |
| | `parse_pdf` | PDF 解析 | `url` | 文本内容 |
| **analyze** | `score` | 多维度质量评分 | `content`, `metadata` | 6 维分数 |
| | `summarize` | 摘要生成 | `content`, `lang` | 摘要 + 要点 |
| | `tag` | 智能标注 | `content` | 难度/类型/概念 |
| | `extract_knowledge` | 知识提取 | `content`, `existing_concepts` | 概念/原理/技术列表 |
| | `discover_relations` | 关系发现 | `new_concepts`, `existing_graph` | 前置/进阶/相关关系 |
| | `compare` | 资源对比 | `resource_a`, `resource_b` | 差异报告 |
| **persist** | `save_resource` | 保存到 SQLite | `resource` | 确认 |
| | `query_db` | 查询数据库 | `sql` / `filter` | 结果集 |
| | `export` | 导出数据 | `format`, `filter` | 文件路径 |
| **render** | `build_learning_system` | 生成学习系统 | `graph`, `path`, `resources` | 站点路径 |
| | `preview` | 启动预览 | `port` | URL |
| | `deploy` | 部署到托管 | `target` | 部署 URL |
| **git** | `checkpoint` | Git 提交 | `message` | commit hash |
| | `log` | 查看提交历史 | `count` | 日志列表 |
| | `diff` | 版本差异 | `v1`, `v2` | 差异报告 |

#### Skill 定义规范

每个 Skill 是一组 LangChain Tools，封装在同一个模块中：

```python
# skills/search.py
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=20, description="最大结果数")

@tool("web_search", args_schema=SearchInput)
async def web_search(query: str, max_results: int = 20) -> list[dict]:
    """从 Google/Bing 搜索网页资源"""
    results = await google_search(query, max_results)
    return [{"url": r.url, "title": r.title, "snippet": r.snippet} for r in results]

# 每个模块导出 Tool 列表
SEARCH_SKILLS = [web_search, arxiv_search, youtube_search, github_search]
```

#### Agent 绑定 Skill

LangGraph Agent 通过 `bind_tools()` 绑定 Skill，详见 §4.0 Supervisor 代码。

#### Skill 注册表

```yaml
# skills.yaml
skills:
  search:  { module: openlearning.skills.search,  tools: [web_search, arxiv_search, youtube_search, github_search] }
  fetch:   { module: openlearning.skills.fetch,   tools: [fetch_page, extract, parse_pdf] }
  analyze: { module: openlearning.skills.analyze,  tools: [score, summarize, tag, extract_knowledge, discover_relations, compare], requires: [fetch] }
  persist: { module: openlearning.skills.persist,  tools: [save_resource, query_db, export] }
  render:  { module: openlearning.skills.render,   tools: [build_learning_system, preview, deploy] }
  git:     { module: openlearning.skills.git,      tools: [checkpoint, log, diff] }
  # 用户自定义
  custom:  { module: ./skills/my_custom.py,        tools: [my_tool] }
```

### 5.3 可观测性 (LangSmith 集成)

**核心价值**：Agent 的行为不透明是最大调试痛点。LangSmith 提供全链路追踪，让每次 LLM 调用、每个 Skill 执行、每条推理链都可追溯、可评估、可回放。

#### 集成架构

```
Agent 运行时
    │
    ├── Skill 执行 ──────┐
    │                     │
    ├── LLM 调用 ─────────┤
    │                     ▼
    ├── 工具调用 ─────► LangSmith
    │                     │
    └── 上下文压缩 ───────┘
                         │
                    ┌────┴────┐
                    ▼         ▼
               Traces    Datasets
               (追踪)    (评估集)
```

#### 追踪维度

| 维度 | 追踪内容 | 用途 |
|------|----------|------|
| **Skill 调用** | 每次 Skill Tool 的输入/输出、耗时、所属模块 | 性能分析、瓶颈定位 |
| **LLM 调用** | prompt、completion、model、token、延迟、成本 | 成本优化、prompt 调优 |
| **链路追踪** | 完整的 Agent 推理链（planner→collector→analyzer→reflector→builder） | 行为回放、异常排查 |
| **上下文压缩** | 压缩前后的 token 数、压缩层级、信息丢失率 | 压缩策略调优 |
| **质量评分** | 每个资源的评分过程、各维度分数、LLM 评分理由 | 评分一致性验证 |

#### LangSmith 面板关键指标

| 指标 | 说明 |
|------|------|
| **总调用 / Token / 成本** | 本周概览，监控用量趋势 |
| **Traces** | 每次 Agent/Skill/LLM 调用的完整链路 |
| **成本趋势** | 日/周/月维度，支持告警阈值 |
| **评估结果** | 评分一致性、摘要质量、分类准确率 |

#### 使用场景

| 场景 | 操作 | 价值 |
|------|------|------|
| **调试异常评分** | 搜索资源 URL → 查看 analyze trace → 定位低分维度 | 快速定位评分偏差原因 |
| **成本优化** | 分析失败调用 → 识别反爬浪费 → 优化预检策略 | 降低无效 token 消耗 |
| **评估数据集** | 从 traces 提取高分样本 → 构建回归测试集 | prompt 修改后自动验证质量 |

#### 配置

```yaml
# openlearning.yaml
langsmith:
  enabled: true
  api_key: ${LANGSMITH_API_KEY}
  project: "openlearning"
  tracing:
    level: "all"                    # all / llm_only / off
  evaluation:
    auto_evaluate: false
    sample_rate: 0.1
  alerts:
    daily_cost_limit: 10.0
```

#### 集成方式

LangGraph + LangSmith 自动集成，Skill Tool 调用和 LLM 调用均自动上报，无需手动 `@traceable`。Agent 级别追踪通过 `@traceable(name="openlearning-agent")` 装饰入口函数即可。

#### 数据保留策略

| 数据类型 | 保留时长 | 说明 |
|----------|----------|------|
| Traces | 30 天 | 自动清理旧 trace |
| Datasets | 永久 | 评估数据集持久保存 |
| 评估结果 | 90 天 | 保留最近 3 个月的评估记录 |
| 成本数据 | 永久 | 用于趋势分析 |

---

## 6. 开发工作流 (`4.C`)

> Agent 自身的开发节奏控制——如何分阶段推进、如何管理上下文生命周期。

### 6.1 Phase 检查点机制 (Git Checkpoint)

**核心问题**：多 Phase 开发任务中，上下文窗口会随进度不断膨胀，导致后续 Phase 推理质量下降、token 浪费。

**解决方案**：每个 Phase 完成后，通过 Git 提交保存进度，清除上下文，下一个 Phase 从 Git 日志恢复状态。

#### 工作流程

```
git log -1 → 解析 phase(N) → 执行 Phase N+1
    │
    ▼
编码 / 测试 / 文档
    │
    ▼
git add -A → git commit "phase(N+1): title ✓" → 清除上下文
    │
    ▼
新上下文 → git log -1 → 解析 phase(N+1) → 执行 Phase N+2
```

#### Commit Message 规范

每条 commit 必须包含 Phase 标记，格式：

```
phase(<N>): <phase_title> ✓

<变更摘要>

completed:
- [x] 子任务 1
- [x] 子任务 2
- [x] 子任务 3

next:
- [ ] Phase N+1 子任务预览
```

**示例**：
```
phase(1): MVP 核心采集 + 生成 ✓

新增 12 个文件，约 2000 行代码

completed:
- [x] CLI / SQLite / Planner Agent
- [x] Google / arXiv / GitHub 采集器
- [x] 内容提取 & 评分 & 站点生成

next:
- [ ] LLM 深度分析 / 多维评分 / 智能摘要
```

#### Phase 状态恢复逻辑

Agent 启动时的决策流程：

```python
def determine_phase(git_log: str) -> int:
    """从 git log 解析当前应执行的 Phase"""
    last_commit = parse_latest_commit(git_log)

    if last_commit is None:
        return 1  # 全新项目，从 Phase 1 开始

    # 解析 "phase(N): ..." 格式
    completed_phase = extract_phase_number(last_commit.message)

    if completed_phase >= MAX_PHASE:
        print("所有 Phase 已完成！")
        return None

    return completed_phase + 1
```

#### 上下文管理策略

| 阶段 | 上下文内容 | 大小估算 |
|------|-----------|----------|
| Phase 启动 | git log (最近 1 条) + PROJECT_SPECS.md 相关章节 + 必要源文件 | ~10-20k tokens |
| Phase 执行中 | 当前任务的代码文件 + 测试 | 动态增长 |
| Phase 结束 | commit 前，确保所有变更已暂存 | — |
| 上下文清除 | 仅保留系统提示 + 完成确认 | ~2k tokens |

#### 安全保障

- Phase 切换前检查 `git status`，有未提交变更则提醒
- commit message 必须包含 `phase(N):` 标记
- 支持 `git revert` 回滚到任意 Phase
- 每次启动显示进度条 `[■■■□□] Phase 3/5`

---

## 7. 数据模型

### 7.1 核心实体

```sql
-- 学习项目
CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,          -- "机器学习入门"
    description TEXT,
    status      TEXT DEFAULT 'active',  -- active / paused / archived
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 主题节点（知识树）
CREATE TABLE topics (
    id          TEXT PRIMARY KEY,
    project_id  TEXT REFERENCES projects(id),
    parent_id   TEXT REFERENCES topics(id),  -- 支持层级
    title       TEXT NOT NULL,
    description TEXT,
    sort_order  INTEGER DEFAULT 0
);

-- 学习资源
CREATE TABLE resources (
    id            TEXT PRIMARY KEY,
    project_id    TEXT REFERENCES projects(id),
    url           TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    source        TEXT NOT NULL,           -- google / arxiv / youtube / ...
    resource_type TEXT NOT NULL,           -- article / video / paper / repo / course
    author        TEXT,
    published_at  DATETIME,
    fetched_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    content_hash  TEXT,                    -- 内容指纹，用于变更检测
    summary       TEXT,                    -- LLM 生成的摘要
    key_points    TEXT,                    -- JSON array of bullet points
    quality_score REAL DEFAULT 0,          -- 综合质量分 0-10
    difficulty    TEXT,                    -- beginner / intermediate / advanced
    reading_time  INTEGER,                -- 预估阅读时间(分钟)
    language      TEXT DEFAULT 'en',
    metadata      TEXT                     -- JSON: 扩展字段
);

-- 资源与主题的多对多关联
CREATE TABLE resource_topics (
    resource_id TEXT REFERENCES resources(id),
    topic_id    TEXT REFERENCES topics(id),
    relevance   REAL DEFAULT 1.0,         -- 相关度 0-1
    PRIMARY KEY (resource_id, topic_id)
);

-- 质量评分明细
CREATE TABLE quality_scores (
    id          TEXT PRIMARY KEY,
    resource_id TEXT REFERENCES resources(id),
    dimension   TEXT NOT NULL,             -- content / teaching / freshness / authority / readability
    score       REAL NOT NULL,             -- 0-10
    reasoning   TEXT                       -- 评分理由
);

-- 采集任务队列
CREATE TABLE crawl_tasks (
    id          TEXT PRIMARY KEY,
    project_id  TEXT REFERENCES projects(id),
    query       TEXT NOT NULL,
    source      TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',   -- pending / running / done / failed
    priority    INTEGER DEFAULT 5,
    result_count INTEGER DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

-- 更新追踪
CREATE TABLE updates (
    id          TEXT PRIMARY KEY,
    resource_id TEXT REFERENCES resources(id),
    change_type TEXT NOT NULL,             -- new / updated / removed
    old_hash    TEXT,
    new_hash    TEXT,
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 7.2 配置文件结构

```yaml
# openlearning.yaml — 用户配置
version: "1.0"

# LLM 配置 (LangChain)
llm:
  provider: openai          # openai / anthropic / ollama(本地)
  model: gpt-4o-mini        # 默认模型（分析用）
  premium_model: gpt-4o     # 高级模型（规划用）
  api_key: ${OPENAI_API_KEY}
  base_url: null            # 自定义 endpoint
  max_tokens: 4096
  temperature: 0.3
  # LangChain 特定配置
  cache: true               # 启用 LangChain LLM 缓存，避免重复调用
  retry_max: 3              # LangChain 内置重试次数
  verbose: false            # 调试模式下打印链的执行细节

# Skill 配置
skills:
  search:
    module: openlearning.skills.search
    enabled: true
    providers:
      google:
        api_key: ${GOOGLE_API_KEY}
        daily_limit: 100
      arxiv: {}  # 无需 API key
      youtube:
        api_key: ${YOUTUBE_API_KEY}
      github:
        token: ${GITHUB_TOKEN}
  fetch:
    module: openlearning.skills.fetch
    enabled: true
    timeout: 30
    respect_robots: true
  analyze:
    module: openlearning.skills.analyze
    enabled: true
  persist:
    module: openlearning.skills.persist
    enabled: true
  render:
    module: openlearning.skills.render
    enabled: true
  git:
    module: openlearning.skills.git
    enabled: true

# 站点生成
site:
  theme: default            # default / minimal / academic
  language: zh-CN
  base_url: "/"
  favicon: null
  analytics: null           # Umami / Plausible 等隐私友好分析

# 更新策略
updates:
  check_interval: weekly    # daily / weekly / monthly
  notify: true
  auto_regenerate: true     # 检测到变更后自动重新生成站点

# LangSmith 可观测性
langsmith:
  enabled: true
  api_key: ${LANGSMITH_API_KEY}
  project: "openlearning"
  tracing:
    level: "all"              # all / llm_only / off
    capture_inputs: true
    capture_outputs: true
  evaluation:
    auto_evaluate: false
    sample_rate: 0.1
  alerts:
    daily_cost_limit: 10.0
    warn_at: 8.0
```

---

## 8. 技术栈选型

### 8.1 后端 / 核心引擎

| 层面 | 选型 | 理由 |
|------|------|------|
| **语言** | Python 3.11+ | AI/爬虫生态最成熟 |
| **CLI 框架** | Typer / Rich | 美观的命令行交互 |
| **异步运行时** | asyncio + aiohttp | 高效并发采集 |
| **数据库** | SQLite (via aiosqlite) | 零配置，单文件部署 |
| **ORM** | SQLModel (Pydantic + SQLAlchemy) | 类型安全 + 序列化 |
| **爬虫** | httpx + BeautifulSoup4 / trafilatura | 内容提取 |
| **LLM 框架** | LangChain + LangGraph | StateGraph 多 Agent 编排、Subgraph 子图、Tool 绑定、条件路由 |
| **Skill 框架** | LangChain Tools + 自定义 BaseSkill | 工具抽象、自动路由、上下文隔离 |
| **上下文管理** | tiktoken + 自定义压缩器 | token 计数、三级压缩、滑动窗口 |
| **可观测性** | LangSmith | 链路追踪、LLM 调用监控、质量评估、成本分析、调试回放 |
| **任务调度** | APScheduler | 定时更新任务 |
| **模板引擎** | Jinja2 | 站点 HTML 生成 |
| **配置管理** | Pydantic Settings | 类型校验 + 环境变量 |

### 8.2 前端 / 生成站点

| 层面 | 选型 | 理由 |
|------|------|------|
| **CSS** | Tailwind CSS (CDN) | 快速构建，无需构建工具 |
| **搜索** | Fuse.js | 轻量客户端全文搜索 |
| **图表** | Mermaid.js | 学习路径可视化 |
| **图标** | Lucide Icons | 轻量 SVG 图标 |
| **部署** | 静态文件 | 兼容任何静态托管 |

### 8.3 外部 API

| API | 用途 | 是否必需 |
|-----|------|----------|
| OpenAI / Anthropic | LLM 分析与规划 | 是 (或用 Ollama 本地替代) |
| LangSmith | 链路追踪、质量评估、成本监控 | 推荐 (有免费额度，可离线运行) |
| SerpAPI / SearchAPI | Google 搜索结果 | 推荐 (有免费额度) |
| YouTube Data API | 视频搜索 | 可选 |
| GitHub API | 代码仓库搜索 | 可选 (免费) |
| arXiv API | 学术论文 | 免费 |
| Bilibili API | 中文视频 | 可选 |

---

## 9. CLI 命令设计

```bash
# 项目管理
openlearning init "机器学习入门"              # 创建新学习项目（交互式）
openlearning init --from-file topic.yaml     # 从配置文件创建
openlearning list                             # 列出所有项目
openlearning status <project-id>             # 查看项目状态

# 资源采集
openlearning collect <project-id>            # 执行一轮完整采集
openlearning collect <project-id> --source arxiv  # 仅从指定源采集
openlearning collect <project-id> --dry-run  # 预览采集计划，不实际执行

# 内容分析
openlearning analyze <project-id>            # 分析所有未处理的资源
openlearning analyze <project-id> --re-score # 重新评估所有资源质量

# 站点生成
openlearning build <project-id>              # 生成静态站点
openlearning build <project-id> --output ./my-site  # 指定输出目录
openlearning serve <project-id>              # 本地预览 (localhost:8080)

# 更新管理
openlearning update check <project-id>       # 检查资源更新
openlearning update apply <project-id>       # 应用更新并重新生成站点

# 导出
openlearning export <project-id> --format markdown  # 导出为 Markdown
openlearning export <project-id> --format json      # 导出为 JSON
openlearning export <project-id> --format anki       # 导出为 Anki 卡片

# Skill 系统
openlearning skill list                            # 列出所有 Skill 及其 Tools
openlearning skill call <skill> <tool> --input '{}' # 手动调用 Skill Tool
openlearning skill test <skill>                    # 测试 Skill 连通性
openlearning skill register ./my-skill.py          # 注册自定义 Skill

# 上下文管理
openlearning context status                        # 查看当前上下文使用情况
openlearning context compress                      # 手动触发上下文压缩
openlearning context snapshot                      # 创建上下文快照

# 可观测性 (LangSmith)
openlearning trace list                            # 查看最近的 trace 记录
openlearning trace show <trace-id>                 # 查看指定 trace 详情
openlearning trace cost                            # 查看成本统计 (日/周/月)
openlearning eval run <dataset>                    # 运行评估数据集
openlearning eval results                          # 查看最近评估结果

# 配置
openlearning config set llm.model gpt-4o     # 修改配置
openlearning config show                      # 查看当前配置
```

---

## 10. 典型工作流

### 10.1 首次使用流程

```
用户: openlearning init "我想学习 Rust 编程"
         │
         ▼
    ┌─────────────────┐
    │ 交互式问答       │
    │ • 你的基础是？   │  → "有 Python 和 C 经验"
    │ • 学习目标是？   │  → "能用 Rust 写 Web 后端"
    │ • 偏好资源类型？ │  → "视频 + 实战教程"
    │ • 语言偏好？     │  → "中英文均可"
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Planner 生成计划 │
    │ • 知识树展开     │
    │ • 搜索关键词矩阵 │
    │ • 采集任务列表   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 自动采集 (2-5分钟)│
    │ • 并行查询多源   │
    │ • 实时进度条     │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 分析 & 评分      │
    │ • 内容提取       │
    │ • 质量评估       │
    │ • 摘要生成       │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 生成站点         │
    │ → ./output/     │
    │ → 自动打开浏览器 │
    └─────────────────┘
```

### 10.2 持续更新流程

```
定时任务 (每周/每日)
         │
         ▼
  ┌──────────────┐
  │ 增量采集      │  ← 仅搜索新内容
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ 变更检测      │  ← 对比 content_hash
  └──────┬───────┘
         │
    ┌────┴────┐
    ▼         ▼
 有变更     无变更
    │         │
    ▼         └→ 结束
  ┌──────────────┐
  │ 重新分析      │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ 重新生成站点   │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ 生成更新报告   │  ← "本周新增 12 个资源，3 个有重大更新"
  └──────────────┘
```

---

## 11. 项目目录结构

```
open_learning/
├── PROJECT_SPECS.md          # 本文档
├── README.md                 # 项目说明
├── pyproject.toml            # 项目配置 & 依赖
├── openlearning.yaml         # 默认配置模板
├── skills.yaml               # Skill 注册表
│
├── src/
│   └── openlearning/
│       ├── __init__.py
│       ├── cli.py            # CLI 入口 (Typer)
│       ├── config.py         # 配置管理 (Pydantic Settings)
│       ├── models.py         # 数据模型 (SQLModel)
│       ├── database.py       # 数据库连接 & 迁移
│       │
│       ├── agents/           # LangGraph Multi-Agent
│       │   ├── __init__.py
│       │   ├── state.py      # AgentState 共享状态定义
│       │   ├── supervisor.py # LLM Supervisor (create_react_agent)
│       │   ├── memory.py     # Memory Agent 子图
│       │   ├── planner.py    # Planner Agent 子图
│       │   ├── collector.py  # Collector Agent 子图
│       │   ├── analyzer.py   # Analyzer Agent 子图 (知识提取)
│       │   ├── evaluator.py  # Evaluation Engine (规则引擎)
│       │   ├── tool_router.py# Tool Router (工具路由)
│       │   ├── reflector.py  # Reflector Agent 子图 (策略反思)
│       │   ├── builder.py    # Builder Agent 子图 (学习系统)
│       │   └── graph.py      # 主图编译 & Skill 绑定
│       │
│       ├── skills/           # Skill 模块 (LangChain Tools)
│       │   ├── __init__.py
│       │   ├── registry.py   # Skill 注册 & 发现
│       │   ├── search.py     # 搜索 Skill (web/arxiv/youtube/github)
│       │   ├── fetch.py      # 抓取 Skill (page/extract/pdf)
│       │   ├── analyze.py    # 分析 Skill (score/summarize/tag/extract_knowledge/discover_relations)
│       │   ├── persist.py    # 持久化 Skill (save/query/export)
│       │   ├── render.py     # 渲染 Skill (build_learning_system/preview/deploy)
│       │   └── git.py        # Git Skill (checkpoint/log/diff)
│       │
│       ├── context/          # 上下文管理
│       │   ├── __init__.py
│       │   ├── manager.py    # ContextManager 主逻辑
│       │   ├── compressor.py # 三级压缩引擎
│       │   ├── memory.py     # 外部记忆 (SQLite 辅助)
│       │   └── snapshot.py   # 上下文快照 & 恢复
│       │
│       ├── monitoring/       # LangSmith 可观测性
│       │   ├── __init__.py
│       │   ├── tracer.py     # 链路追踪初始化 & 配置
│       │   ├── evaluator.py  # LLM 输出质量评估
│       │   ├── cost.py       # 成本追踪 & 告警
│       │   └── dashboard.py  # 本地面板数据聚合
│       │
│       ├── templates/        # Jinja2 模板 (Builder Skill 使用)
│           ├── base.html
│           ├── index.html
│           ├── learning_path.html
│           ├── resources.html
│           ├── timeline.html
│           └── components/
│               ├── header.html
│               ├── footer.html
│               ├── resource_card.html
│               ├── search.html
│               └── stats.html
│
├── static/                   # 静态资源
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js
│   │   ├── search.js
│   │   └── bookmarks.js
│   └── images/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_planner.py
│   ├── test_collectors.py
│   ├── test_analyzer.py
│   ├── test_builder.py
│   └── fixtures/             # 测试数据
│
└── docs/
    ├── getting-started.md
    ├── configuration.md
    ├── deployment.md
    └── contributing.md
```

---

## 12. 开发路线图

### Phase 1: MVP (核心采集 + 生成) — 2 周

- [x] 项目脚手架搭建
- [ ] CLI 基础框架 (init / collect / build / serve)
- [ ] SQLite 数据模型
- [ ] Planner Agent (LLM 驱动的学习路径规划)
- [ ] Google 搜索采集器
- [ ] arXiv 论文采集器
- [ ] GitHub 仓库采集器
- [ ] 基础内容提取 & 质量评分
- [ ] 静态站点生成 (单主题资源列表)
- [ ] 本地预览服务器

### Phase 2: 智能分析 — 1 周

- [ ] LLM 驱动的深度内容分析
- [ ] 多维度质量评分引擎
- [ ] 智能摘要生成
- [ ] 去重 & 相似度检测
- [ ] 难度自动标注

### Phase 3: 丰富站点 — 1 周

- [ ] 学习路径可视化 (Mermaid)
- [ ] 多维度浏览 (按主题/难度/类型/时间线)
- [ ] 客户端搜索 (Fuse.js)
- [ ] 个人收藏夹 (localStorage)
- [ ] 暗色模式
- [ ] 响应式设计优化

### Phase 4: 持续更新 — 1 周

- [ ] 增量采集引擎
- [ ] 内容变更检测
- [ ] 定时任务调度
- [ ] 更新报告生成
- [ ] 自动重新构建

### Phase 5: 扩展 & 打磨 — 持续

- [ ] 更多数据源 (Bilibili, 知乎, Coursera)
- [ ] Anki 卡片导出
- [ ] Markdown 导出
- [ ] 多项目管理
- [ ] 插件系统 (自定义采集器)
- [ ] Web UI 管理面板
- [ ] Docker 部署

---

## 13. 质量评估维度详解

| 维度 | 权重 | 评估方式 | 说明 |
|------|------|----------|------|
| **内容深度** | 25% | LLM 评估 | 是否深入讲解，而非浅尝辄止 |
| **教学质量** | 20% | LLM 评估 | 是否有清晰的结构、示例、练习 |
| **时效性** | 20% | 规则 + LLM | 发布日期、技术版本是否过时 |
| **权威性** | 15% | 规则 | 作者/平台声誉、引用数、Star 数 |
| **可读性** | 10% | 规则 | 排版质量、语言流畅度 |
| **实操性** | 10% | LLM 评估 | 是否有可运行的代码、动手练习 |

**评分公式**：
```
final_score = Σ(dimension_score × weight) × freshness_multiplier

freshness_multiplier:
  age < 6个月   → 1.0
  6月 < age < 2年 → 0.85
  2年 < age < 5年 → 0.7
  age > 5年      → 0.5 (除非是经典内容)
```

---

## 14. 错误处理与容错

| 场景 | 策略 |
|------|------|
| LLM API 限流 | 指数退避重试，最大 3 次 |
| 搜索 API 额度耗尽 | 降级到 DuckDuckGo (免费) |
| 网页抓取失败 | 跳过并记录，不阻塞整体流程 |
| 内容提取失败 | 使用 URL + title + 元数据作为最低质量记录 |
| LLM 输出格式异常 | 正则提取 + 重试，最终降级为默认值 |
| 数据库锁定 | WAL 模式 + 连接池 |

---

## 15. 性能指标

| 指标 | 目标值 |
|------|--------|
| 单次完整采集 (50 个资源) | < 5 分钟 |
| 内容分析 (50 个资源) | < 10 分钟 |
| 站点生成 | < 30 秒 |
| 搜索请求延迟 | < 2 秒/请求 |
| 数据库查询 | < 100ms |
| 生成站点首屏加载 | < 1 秒 |
| 搜索响应 (客户端) | < 200ms |

---

## 16. 安全与合规

- **API Key 管理**：通过环境变量或 `.env` 文件，绝不硬编码
- **robots.txt**：默认遵守，可通过配置关闭
- **请求频率**：内置限流器，避免对目标站点造成压力
- **内容版权**：仅存储摘要和元数据，不缓存全文
- **用户数据**：所有数据本地存储，不上传到任何云服务
- **依赖安全**：定期 `pip-audit` 检查依赖漏洞

---

## 17. 测试策略

| 层级 | 工具 | 覆盖目标 |
|------|------|----------|
| 单元测试 | pytest | 核心逻辑 > 90% |
| 集成测试 | pytest + httpx | 采集器 + LLM 调用 (mock) |
| E2E 测试 | pytest + tmp_path | 完整 init → collect → build 流程 |
| 站点测试 | Playwright | 生成站点的 UI 验证 |
| 性能测试 | pytest-benchmark | 评分引擎、去重算法 |

---

*本文档将随项目演进持续更新。最后更新：2026-06-18*
