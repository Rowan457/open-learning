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
│         ┌─────────┬───────────┼───────────┬─────────┐              │
│         ▼         ▼           ▼           ▼         ▼              │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐     │
│  │ Planner  ││Collector ││ Analyzer ││ Reflector││ Builder  │     │
│  │  Agent   ││  Agent   ││  Agent   ││  Agent   ││  Agent   │     │
│  │          ││          ││          ││          ││          │     │
│  │ 子图:    ││ 子图:    ││ 子图:    ││ 子图:    ││ 子图:    │     │
│  │ 规划→展开││ 搜索→抓取││ 评分→摘要││ 审查→补缺││ 渲染→部署│     │
│  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘     │
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
| **StateGraph** | open_deep_research | 全局状态驱动，Agent 通过读写共享状态协作 |
| **Supervisor 路由** | open_deep_research | Supervisor 根据当前状态决定下一个执行的 Agent |
| **Sub-Agent 子图** | open_deep_research | 每个 Agent 是独立的 LangGraph 子图，可独立测试 |
| **Reflection 循环** | open_deep_research | Reflector Agent 审查结果，决定是否需要补充采集 |
| **条件边路由** | open_deep_research | 基于状态字段的条件分支（如资源数量不足→重新采集） |
| **Skill 模块化** | LangChain Tools | 所有外部能力（搜索/抓取/分析/持久化/渲染）封装为独立 Skill，Agent 通过 Tool 接口调用 |
| **Human-in-the-loop** | open_deep_research | 关键节点支持人工确认（如学习计划审批） |

### 3.3 Graph 流程

```
START
  │
  ▼
┌─────────────┐
│   Planner   │  ← 分析需求，生成知识树 + 采集计划
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Collector  │  ← 按计划并行采集（可多轮）
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Analyzer   │  ← 质量评分 + 摘要生成
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│  Reflector  │────▶│  Collector  │  ← 资源不足？质量不达标？补充采集
└──────┬──────┘     └─────────────┘
       │ (通过)
       ▼
┌─────────────┐
│   Builder   │  ← 生成静态站点
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

#### Supervisor（主图编排器）

Supervisor 是 LangGraph 主图的路由节点，不执行具体任务，而是根据共享状态决定下一步调用哪个 Sub-Agent。

```python
from langgraph.graph import StateGraph, START, END

class AgentState(TypedDict):
    """所有 Agent 共享的全局状态"""
    # 用户输入
    user_request: str                    # "我想学 Rust"
    user_profile: dict                   # {"level": "intermediate", "lang": ["zh","en"]}

    # Planner 输出
    learning_plan: dict                  # 知识树 + 采集任务列表
    search_queries: list[str]            # 生成的搜索关键词

    # Collector 输出
    raw_resources: list[dict]            # 采集到的原始资源
    collected_count: int                 # 已采集数量

    # Analyzer 输出
    analyzed_resources: list[dict]       # 评分 + 摘要后的资源
    avg_quality_score: float             # 平均质量分

    # Reflector 输出
    reflection: dict                     # {"pass": bool, "gaps": [...], "suggestions": [...]}
    iteration: int                       # 当前迭代轮次
    max_iterations: int                  # 最大迭代轮次

    # Builder 输出
    site_path: str                       # 生成的站点路径

    # 流程控制
    current_agent: str                   # 当前执行的 Agent 名
    status: str                          # running / done / error

def supervisor_router(state: AgentState) -> str:
    """Supervisor 路由逻辑：根据状态决定下一个 Agent"""
    if state.get("status") == "done":
        return END

    current = state.get("current_agent", "")

    # 首次进入
    if not current:
        return "planner"

    # 状态机路由
    transitions = {
        "planner":  "collector",
        "collector": "analyzer",
        "analyzer":  "reflector",
        "reflector": "builder" if state["reflection"]["pass"] else "collector",
        "builder":   END,
    }
    return transitions.get(current, END)

# 主图定义
graph = StateGraph(AgentState)
graph.add_node("planner", planner_agent)
graph.add_node("collector", collector_agent)
graph.add_node("analyzer", analyzer_agent)
graph.add_node("reflector", reflector_agent)
graph.add_node("builder", builder_agent)

graph.add_edge(START, "planner")
graph.add_conditional_edges("planner", supervisor_router)
graph.add_conditional_edges("collector", supervisor_router)
graph.add_conditional_edges("analyzer", supervisor_router)
graph.add_conditional_edges("reflector", supervisor_router)
graph.add_conditional_edges("builder", supervisor_router)

app = graph.compile()
```

#### 状态流转图

```
START
  │
  ▼
┌─────────┐    state["learning_plan"]
│ Planner │───────────────────────────────────┐
└─────────┘                                   │
                                              ▼
┌─────────┐    state["raw_resources"]    ┌──────────┐
│Analyzer │◀─────────────────────────────│Collector │
└────┬────┘                              └──────────┘
     │                                        ▲
     ▼                                        │
┌───────────┐   state["reflection"]["pass"]   │
│ Reflector │──── false (有缺口) ─────────────┘
└────┬──────┘
     │ true (通过)
     ▼
┌─────────┐    state["site_path"]
│ Builder │──────────────▶ END
└─────────┘
```

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

### 4.3 Analyzer Agent（内容分析子图）

**职责**：对采集到的原始资源进行内容提取、质量评估、智能标注和摘要生成。

```python
def analyzer_agent(state: AgentState) -> dict:
    """Analyzer 子图：通过 Skill 内容提取 → 评分 → 标注 → 摘要"""
    resources = state["raw_resources"]
    analyzed = []

    for resource in resources:
        # 1. 内容提取（调用 fetch Skill）
        content = await fetch_page.ainvoke({"url": resource["url"]})

        # 2. 质量评分（调用 analyze Skill）
        scores = await score.ainvoke({
            "content": content, "metadata": resource.get("metadata", {})
        })

        # 3. 智能标注（调用 analyze Skill）
        tags = await tag.ainvoke({"content": content})

        # 4. 摘要生成（调用 analyze Skill）
        summary = await summarize.ainvoke({"content": content, "lang": "zh"})

        analyzed.append({
            **resource,
            "content_preview": content[:500],
            "quality_scores": scores,
            "quality_score": weighted_average(scores.values()),
            "tags": tags,
            "summary": summary,
        })

    # 5. 持久化（调用 persist Skill）
    for res in analyzed:
        await save_resource.ainvoke({"resource": res})

    avg_score = mean([r["quality_score"] for r in analyzed])
    return {
        "analyzed_resources": analyzed,
        "avg_quality_score": avg_score,
        "current_agent": "analyzer",
    }
```

**输出写入状态**：`analyzed_resources`, `avg_quality_score`

#### 分析流水线

```
原始资源 (URL + 元数据)
         │
         ▼
  ┌──────────────┐
  │ 内容提取      │  ← 正文提取 (readability/trafilatura)
  │              │     代码块保留
  │              │     元数据提取 (作者、日期、标签)
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ 质量评估      │  ← 多维度打分 (0-10)
  │ (LLM + 规则) │
  └──────┬───────┘
         │
         ├── 内容质量: 深度、准确性、原创性
         ├── 教学质量: 结构清晰度、示例丰富度、难度标注
         ├── 时效性:   发布日期、技术版本是否过时
         ├── 权威性:   作者背景、平台可信度、引用/点赞数
         └── 可读性:   排版、语言流畅度、多媒体丰富度
         │
         ▼
  ┌──────────────┐
  │ 智能标注      │
  └──────┬───────┘
         │
         ├── 难度标签: beginner / intermediate / advanced
         ├── 内容类型: tutorial / deep-dive / overview / hands-on
         ├── 前置知识: 需要先学什么
         ├── 关键概念: 涵盖的核心知识点
         └── 预估时长: 阅读/观看所需时间
         │
         ▼
  ┌──────────────┐
  │ 摘要生成      │  ← LLM 生成 3-5 句话的中文摘要
  │ (LLM 驱动)   │     提取核心要点 (3-5 个 bullet points)
  └──────────────┘
```

### 4.4 Reflector Agent（审查反馈子图）

**职责**：审查 Analyzer 的输出，判断资源是否充足、质量是否达标，决定是否需要补充采集。这是实现 open_deep_research 中 **Reflection 循环** 的关键节点。

```python
class ReflectorState(TypedDict):
    analyzed_resources: list[dict]
    learning_plan: dict
    reflection: dict          # {"pass": bool, "gaps": [...], "suggestions": [...]}
    iteration: int

def reflector_agent(state: AgentState) -> dict:
    """Reflector 子图：审查资源质量 → 识别缺口 → 决定是否重采"""
    resources = state["analyzed_resources"]
    plan = state["learning_plan"]
    iteration = state.get("iteration", 0)

    # 1. 覆盖度检查：每个子主题是否有足够资源？
    coverage = check_topic_coverage(resources, plan["tree"])

    # 2. 质量检查：平均分是否达标？
    avg_score = state.get("avg_quality_score", 0)
    quality_ok = avg_score >= 6.0

    # 3. 多样性检查：资源类型是否多样？
    diversity = check_type_diversity(resources)

    # 4. 生成反思报告
    gaps = []
    if coverage["missing_topics"]:
        gaps.append(f"缺少主题覆盖: {coverage['missing_topics']}")
    if not quality_ok:
        gaps.append(f"平均质量分 {avg_score:.1f} 低于阈值 6.0")
    if diversity["missing_types"]:
        gaps.append(f"缺少资源类型: {diversity['missing_types']}")

    passed = len(gaps) == 0 or iteration >= state.get("max_iterations", 3)

    return {
        "reflection": {
            "pass": passed,
            "gaps": gaps,
            "suggestions": generate_suggestions(gaps),
            "coverage": coverage,
        },
        "iteration": iteration + 1,
        "current_agent": "reflector",
    }
```

**输出写入状态**：`reflection`, `iteration`

**路由逻辑**：
- `reflection["pass"] == False` → Supervisor 路由回 Collector，补充采集
- `reflection["pass"] == True` → Supervisor 路由到 Builder

#### 审查维度

| 维度 | 检查内容 | 不达标处理 |
|------|----------|-----------|
| **主题覆盖** | 每个子主题至少 3 个资源 | 生成补充搜索词 → Collector |
| **质量门槛** | 平均分 ≥ 6.0，无低于 3 分的资源 | 淘汰低分，补充新源 |
| **类型多样性** | 至少覆盖 3 种资源类型 | 针对缺失类型定向搜索 |
| **时效性** | 最近 1 年的资源占比 ≥ 30% | 增加时间限定搜索 |
| **难度分布** | beginner/intermediate/advanced 均有覆盖 | 针对缺失难度补充 |

---

### 4.5 Builder Agent（站点生成子图）

**职责**：将分析后的资源组织成可浏览的静态课程网站。

```python
class BuilderState(TypedDict):
    analyzed_resources: list[dict]
    learning_plan: dict
    site_path: str

def builder_agent(state: AgentState) -> dict:
    """Builder 子图：通过 Skill 生成静态站点"""
    resources = state["analyzed_resources"]
    plan = state["learning_plan"]

    # 1. 调用 render Skill 生成站点
    site_path = await build_site.ainvoke({
        "resources": resources,
        "plan": plan,
        "output_dir": "./output/",
    })

    # 2. 调用 git Skill 自动提交
    await checkpoint.ainvoke({
        "message": f"build: generate site with {len(resources)} resources"
    })

    return {
        "site_path": site_path,
        "current_agent": "builder",
        "status": "done",
    }
```

**输出写入状态**：`site_path`, `status`

#### 生成的站点结构

```
output/
├── index.html                # 首页：学习主题概览 + 学习路径图
├── learning-path.html        # 学习路径：阶段化推荐
├── resources/
│   ├── by-topic/             # 按主题分类
│   │   ├── fundamentals.html
│   │   ├── deep-learning.html
│   │   └── nlp.html
│   ├── by-difficulty/        # 按难度分层
│   │   ├── beginner.html
│   │   ├── intermediate.html
│   │   └── advanced.html
│   ├── by-type/              # 按资源类型
│   │   ├── videos.html
│   │   ├── articles.html
│   │   ├── papers.html
│   │   └── repos.html
│   └── timeline.html         # 时间线：最新资源动态
├── search.html               # 客户端搜索 (Fuse.js)
├── bookmarks.html            # 个人收藏 (本地存储)
├── changelog.html            # 更新日志
├── assets/
│   ├── css/style.css
│   ├── js/app.js
│   └── images/
└── data/
    ├── resources.json        # 结构化资源数据
    └── search-index.json     # 搜索索引
```

#### 站点特性

| 特性 | 实现方案 |
|------|----------|
| 框架 | 纯静态 HTML + Tailwind CSS (零依赖，即开即用) |
| 搜索 | Fuse.js 客户端全文搜索 |
| 收藏 | localStorage 本地收藏夹 |
| 响应式 | Mobile-first 设计 |
| 暗色模式 | CSS 变量 + 系统偏好检测 |
| 学习路径 | Mermaid.js 可视化知识图谱 |
| SEO | 语义化 HTML + meta 标签 |
| 部署 | 支持 Vercel / Netlify / GitHub Pages 一键部署 |

## 5. Agent 基础设施 (`4.B`)

> 运行时支撑层——不直接面向用户，但决定了 Agent 的效率、质量和可维护性。

### 5.1 上下文压缩 (Context Compression)

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
    ├── analyze Skill  → score / summarize / tag / compare
    ├── persist Skill  → save_resource / query_db / export
    ├── render Skill   → build_site / preview / deploy
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
| | `compare` | 资源对比 | `resource_a`, `resource_b` | 差异报告 |
| **persist** | `save_resource` | 保存到 SQLite | `resource` | 确认 |
| | `query_db` | 查询数据库 | `sql` / `filter` | 结果集 |
| | `export` | 导出数据 | `format`, `filter` | 文件路径 |
| **render** | `build_site` | 生成静态站点 | `resources`, `plan` | 站点路径 |
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
  analyze: { module: openlearning.skills.analyze,  tools: [score, summarize, tag, compare], requires: [fetch] }
  persist: { module: openlearning.skills.persist,  tools: [save_resource, query_db, export] }
  render:  { module: openlearning.skills.render,   tools: [build_site, preview, deploy] }
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
│       │   ├── supervisor.py # Supervisor 主图路由
│       │   ├── planner.py    # Planner Agent 子图
│       │   ├── collector.py  # Collector Agent 子图
│       │   ├── analyzer.py   # Analyzer Agent 子图
│       │   ├── reflector.py  # Reflector Agent 子图
│       │   ├── builder.py    # Builder Agent 子图
│       │   └── graph.py      # 主图编译 & Skill 绑定
│       │
│       ├── skills/           # Skill 模块 (LangChain Tools)
│       │   ├── __init__.py
│       │   ├── registry.py   # Skill 注册 & 发现
│       │   ├── search.py     # 搜索 Skill (web/arxiv/youtube/github)
│       │   ├── fetch.py      # 抓取 Skill (page/extract/pdf)
│       │   ├── analyze.py    # 分析 Skill (score/summarize/tag)
│       │   ├── persist.py    # 持久化 Skill (save/query/export)
│       │   ├── render.py     # 渲染 Skill (build/preview/deploy)
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
