# OpenLearning

AI 驱动的个人学习信息系统 — 告诉它你想学什么，它帮你把整个互联网变成一本结构化的教科书。

## 功能特性

- 🔍 **智能采集** — 从 Google、arXiv、YouTube、GitHub 等多源并行采集学习资源
- 🧠 **知识提取** — 自动从资源中提取概念、原理、技术，构建知识图谱
- 📊 **质量评估** — 多维度规则评分 + LLM 深度分析
- 🗺️ **知识图谱** — 交互式知识图谱可视化，全局理解知识结构
- 📚 **学习路径** — 基于拓扑排序的个性化学习路径
- 🔄 **间隔重复** — SM-2 算法调度复习，防止遗忘
- 💾 **学习记忆** — 三层记忆系统（项目/偏好/学习），越用越懂你

## 快速开始

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd open_learning

# 安装依赖
pip install -e .

# 或使用 uv
uv pip install -e .
```

### 配置

```bash
# 复制配置模板
cp openlearning.yaml ~/.openlearning/config.yaml

# 设置环境变量
export MIMO_API_KEY="your-api-key"
export MIMO_BASE_URL="https://api.mimo.ai/v1"

# 可选：搜索 API
export GOOGLE_API_KEY="your-google-key"
export YOUTUBE_API_KEY="your-youtube-key"
export GITHUB_TOKEN="your-github-token"
```

### 使用

```bash
# 创建学习项目
openlearning init "我想学 Rust 编程"

# 查看项目列表
openlearning list

# 执行采集
openlearning collect <project-id>

# 预览采集计划（不实际执行）
openlearning collect <project-id> --dry-run

# 启动预览服务器
openlearning serve <project-id>

# 导出数据
openlearning export <project-id> --format markdown
```

## 架构

OpenLearning 采用 **LangGraph Multi-Agent** 架构：

```
用户输入 → Supervisor → Memory → Planner → Collector → Analyzer → Evaluator → Builder → 学习系统
```

每个 Agent 是独立的 LangGraph 子图，通过共享状态协作：

| Agent | 职责 |
|-------|------|
| **Supervisor** | LLM 决策者，编排所有 Agent |
| **Memory** | 三层记忆：项目/偏好/学习 |
| **Planner** | 需求分析 → 知识树 → 搜索词 |
| **Collector** | 多源并行采集 → 去重 → 持久化 |
| **Analyzer** | 二阶段分析：规则预筛 → LLM 深度分析 |
| **Evaluator** | 规则引擎：质量/覆盖/多样性检查 |
| **Reflector** | 策略反思：根因分析 → 调整建议 |
| **Builder** | 知识图谱 → 学习路径 → 静态站点 |

## 技术栈

- **语言**: Python 3.11+
- **Agent**: LangGraph + LangChain
- **LLM**: 小米 MiMo (mimo-v2.5-pro / mimo-v2.5 / mimo-7b)
- **数据库**: SQLite (SQLModel)
- **CLI**: Typer + Rich
- **爬虫**: httpx + trafilatura
- **模板**: Jinja2
- **可观测**: LangSmith

## 项目结构

```
open_learning/
├── src/openlearning/
│   ├── cli.py            # CLI 入口
│   ├── config.py         # 配置管理
│   ├── models.py         # 数据模型
│   ├── database.py       # 数据库层
│   ├── agents/           # LangGraph Agent 子图
│   ├── skills/           # Skill 模块 (LangChain Tools)
│   ├── context/          # 上下文管理
│   ├── memory/           # 学习记忆系统
│   ├── monitoring/       # LangSmith 可观测性
│   └── templates/        # Jinja2 模板
├── tests/                # 测试
├── openlearning.yaml     # 配置文件
└── pyproject.toml        # 项目配置
```

## 开发路线图

- [x] Phase 1: MVP (核心采集 + 生成)
- [ ] Phase 2: 智能分析 (LLM 深度分析)
- [ ] Phase 3: 丰富站点 (交互式图谱、搜索)
- [ ] Phase 4: 持续更新 (增量采集、变更检测)
- [ ] Phase 5: 扩展 & 打磨

## License

MIT
