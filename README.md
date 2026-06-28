# OpenLearning

AI 驱动的个人学习信息系统 — 告诉它你想学什么，它帮你把整个互联网变成一本结构化的教科书。

## 功能特性

- 🔍 **智能采集** — 从 Google、arXiv、YouTube、GitHub、Bilibili、知乎等多源并行采集
- 🧠 **知识提取** — LLM 自动提取概念、原理、技术，构建知识图谱
- 📊 **质量评估** — 多维度规则评分（质量/覆盖/多样性/时效性）
- 🗺️ **知识图谱** — 交互式可视化，全局理解知识结构
- 📚 **学习路径** — 基于拓扑排序的个性化学习路径
- 🔄 **间隔重复** — SM-2 算法调度复习，防止遗忘
- 💾 **学习记忆** — 三层记忆系统（项目/偏好/学习），越用越懂你
- 🔌 **插件系统** — 自定义数据源采集器（RSS、豆瓣等）
- 📡 **LangSmith** — 全链路追踪，可观测每次 LLM 调用和工具执行

## 快速开始

### 安装

```bash
git clone <repo-url>
cd open_learning

# 使用 uv（推荐）
uv pip install -e .

# 或 pip
pip install -e .
```

### 配置

复制 `.env.example` 为 `.env`，填入必要配置：

```bash
# LLM（必填）
MIMO_API_KEY=your-api-key
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1

# 搜索 API（可选，无 key 则降级到免费源）
TAVILY_API_KEY=your-tavily-key
YOUTUBE_API_KEY=your-youtube-key
GITHUB_TOKEN=your-github-token

# LangSmith 可观测性（可选）
LANGSMITH_API_KEY=your-langsmith-key

# 代理（国内访问 YouTube 等需要）
# HTTP_PROXY=http://127.0.0.1:7890
# HTTPS_PROXY=http://127.0.0.1:7890
```

### 使用

```bash
# 创建学习项目
openlearning init "我想学 Rust 编程"

# 查看项目列表
openlearning list

# 执行采集
openlearning collect <project-id>

# 启动 Web UI
openlearning web

# 导出数据
openlearning export <project-id> --format markdown
```

## 架构

OpenLearning 采用 **三层嵌套 LangGraph** 架构：

```
主图 (AgentState)
├── preprocess       → Memory + Planner（串行）
├── supervisor 子图   → Supervisor 决策循环（嵌套）
│   ├── supervisor        → LLM 决策（绑定工具）
│   └── supervisor_tools  → 执行工具 / 并行调度 Worker
│       └── Worker 子图（并行 ×N）
│           ├── worker        → LLM 调用搜索/分析工具
│           ├── worker_tools  → 并行执行工具
│           └── compress      → 压缩结果返回
└── postprocess      → 提取知识点 + Builder 生成学习系统
```

**核心设计**：
- 每层独立编译、独立状态，通过字段对齐通信
- `asyncio.gather` 并行调度多个 Worker
- `override_reducer` 实现消息覆盖（重置上下文）
- `output=WorkerOutputState` 过滤 Worker 输出（只返回压缩结果）

### 组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **主图** | `agents/graph.py` | 端到端流程编排 |
| **Supervisor 子图** | `agents/subgraphs/supervisor.py` | 决策循环 + 并行 Worker 调度 |
| **Worker 子图** | `agents/subgraphs/worker.py` | ReAct 循环 + 压缩输出 |
| **工具** | `agents/tools.py` | Supervisor/Worker 工具定义 |
| **Prompt** | `agents/prompts.py` | 集中管理 Prompt 模板 |
| **状态** | `agents/state.py` | AgentState / SupervisorState / WorkerState |

### 工具集

**Supervisor 工具**：`ConductResearch`、`ResearchComplete`、`think_tool`、`EvaluateQuality`

**Worker 工具**：`web_search`、`arxiv_search`、`youtube_search`、`github_search`、`fetch_page`、`save_resource`、`summarize`、`extract_knowledge`、`llm_summarize`、`plugin_search`

## 技术栈

- **语言**: Python 3.11+
- **Agent**: LangGraph + LangChain
- **LLM**: 小米 MiMo（mimo-v2.5-pro / mimo-v2.5 / mimo-7b）
- **数据库**: SQLite（SQLModel）
- **Web**: FastAPI + Vue 3
- **CLI**: Typer + Rich
- **爬虫**: httpx + trafilatura + BeautifulSoup
- **可观测**: LangSmith
- **包管理**: uv

## 项目结构

```
open_learning/
├── src/openlearning/
│   ├── agents/                # 三层嵌套 Agent
│   │   ├── graph.py           # 主图编译
│   │   ├── state.py           # 状态定义
│   │   ├── tools.py           # Supervisor/Worker 工具
│   │   ├── prompts.py         # Prompt 模板
│   │   ├── subgraphs/         # 子图实现
│   │   │   ├── supervisor.py  # Supervisor 子图
│   │   │   └── worker.py      # Worker 子图
│   │   ├── collector.py       # 资源采集逻辑
│   │   ├── builder.py         # 知识图谱 + 学习系统生成
│   │   ├── planner.py         # 需求分析 + 搜索词生成
│   │   ├── memory.py          # 三层记忆查询
│   │   ├── evaluator.py       # 规则引擎评估
│   │   └── updater.py         # 增量更新
│   ├── tools/                 # LangChain Tools
│   │   ├── search.py          # 搜索工具（多源）
│   │   ├── fetch.py           # 网页抓取
│   │   ├── analyze.py         # 内容分析
│   │   ├── persist.py         # 数据持久化
│   │   ├── memory.py          # 记忆工具
│   │   └── render.py          # 站点生成
│   ├── plugins/               # 插件系统
│   │   ├── base.py            # BaseCollector 抽象类
│   │   └── manager.py         # 插件发现/加载/管理
│   ├── memory/                # 学习记忆算法
│   ├── monitoring/            # LangSmith + 成本追踪
│   ├── web/                   # FastAPI Web UI
│   │   ├── api.py             # REST API
│   │   ├── app.py             # FastAPI 应用
│   │   └── frontend/          # Vue 3 前端
│   ├── config.py              # 配置管理
│   ├── database.py            # 数据库层
│   ├── models.py              # SQLModel 数据模型
│   ├── llm.py                 # LLM 客户端
│   └── cli.py                 # CLI 入口
├── plugins/                   # 用户自定义插件
├── tests/                     # 测试
├── openlearning.yaml          # 主配置文件
├── .env                       # 环境变量（不提交）
└── pyproject.toml             # 项目配置
```

## 插件系统

在 `plugins/` 目录创建 `BaseCollector` 子类即可自动发现：

```python
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

class MyCollector(BaseCollector):
    @property
    def meta(self):
        return PluginMeta(name="my-source", source_type="custom")

    async def search(self, query, max_results=20, **kwargs):
        return [SearchResult(url="...", title="...", snippet="...")]
```

已有插件：`example_rss`（RSS 订阅）、`douban_movies`（豆瓣电影）

## 开发路线图

- [x] Phase 1: MVP（核心采集 + 生成）
- [x] Phase 2: 智能分析（LLM 深度分析）
- [x] Phase 3: 三层嵌套 Agent 架构
- [x] Phase 4: LangSmith 可观测性
- [x] Phase 5: 插件系统 + 代理支持
- [ ] Phase 6: 丰富站点（交互式图谱、搜索）
- [ ] Phase 7: 持续更新（定时采集、变更通知）

## License

MIT
