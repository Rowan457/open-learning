# Changelog

All notable changes to this project will be documented in this file.

Format: `phase(<N>): <title> ✓`

---

## phase(0): 项目初始化 ✓

**日期**: 2026-06-18

### 创建文件
- `PROJECT_SPECS.md` — 完整项目规格文档 (v1.0)
- `CHANGELOG.md` — 版本变更日志
- `.gitignore` — Git 忽略规则

### Specs 核心内容
1. 项目愿景与用户场景
2. LangGraph Multi-Agent 架构 (Supervisor + 5 Sub-Agent)
3. 5 个功能 Agent: Planner / Collector / Analyzer / Reflector / Builder
4. Agent 基础设施: 上下文压缩 / Skill 系统 / LangSmith 可观测性
5. 开发工作流: Git Phase 检查点机制
6. 数据模型 (SQLite)
7. 技术栈选型
8. CLI 命令设计
9. 典型工作流
10. 项目目录结构
11. 开发路线图 (5 Phase)
12. 质量评估 / 错误处理 / 性能 / 安全 / 测试策略

### 关键设计决策
- **LLM 框架**: LangChain + LangGraph (StateGraph 多 Agent 编排)
- **工具系统**: Skill 模块化 (LangChain Tools)，非 MCP
- **可观测性**: LangSmith 全链路追踪
- **上下文管理**: 三级压缩 (滑动窗口 → 工具输出压缩 → 决策日志)
- **开发节奏**: Git Phase 检查点，每个 Phase 完成后 commit + 清上下文

---

## phase(0.1): 优化排版 ✓

**日期**: 2026-06-18

### 优化内容
- 修复架构图重复 LangSmith 节点
- 恢复 §4.A 功能 Agent 分组头，§5/§6 标注 4.B/4.C 归属
- 精简 §5.1 上下文压缩: 三张规则表合并为一张，生命周期图压缩为 5 行
- 精简 §5.2 Skill 系统: 删除重复架构图/绑定代码/注册 YAML
- 精简 §5.3 LangSmith: 删除 ASCII 面板/场景详情/集成代码
- 精简 §6.1 工作流: 压缩流程图/commit 示例/安全保障
- 清理目录结构: 移除 collectors/pipeline/builder 冗余目录

### 效果
- 1801 行 → 1510 行 (-16%)
- 86 行新增，377 行删除

---

---

## phase(0.2): 架构升级 ✓

**日期**: 2026-06-18

### 6 项重大改动

1. **Supervisor → LLM 决策者** — 状态机查表改为 LLM 推理决策
2. **新增 Tool Router** — LLM 选择最佳工具组合，避免硬编码
3. **Analyzer → 知识提取** — 从评分摘要升级为概念提取+关系发现
4. **新增 Memory Agent** — 学习用户偏好、历史项目、去重推荐
5. **新增 Evaluation Engine** — 规则引擎做质量/覆盖检查，零 token 成本
6. **Builder → 学习系统** — 从资源列表升级为知识图谱学习系统

### 新 Agent 列表
- Supervisor (LLM) / Memory / Planner / Collector / Analyzer
- Evaluation Engine (规则) / Tool Router / Reflector / Builder

---

---

## phase(0.3): MiMo 模型 + 成本优化 ✓

**日期**: 2026-06-18

### LLM → 小米 MiMo
- mimo-v2.5-pro: Supervisor / Planner / Reflector
- mimo-v2.5: Analyzer / Tool Router
- mimo-7b: 标注 / 摘要 / Builder

### 成本优化策略
1. 先筛选再读 — 规则预筛淘汰低质量资源
2. 二阶段分析 — 规则评分(零成本) → 高分资源进 LLM
3. 模型分层 — 不同任务用不同模型
4. 缓存去重 — LLM 缓存 + URL/知识/搜索去重

### 效果
- 单次流程成本: < $0.50 (50 资源)
- LLM 调用: < 60 次 (原 ~200 次)

---

---

## phase(0.4): Learning Memory 系统 ✓

**日期**: 2026-06-18

### 三层记忆架构
1. **项目记忆** — 历史项目、已推荐 URL、相似项目检测
2. **偏好记忆** — 资源类型/语言/难度/学习风格
3. **学习记忆** ★ — 概念掌握度、学习轨迹、间隔重复、知识缺口

### 新增数据表
- concepts / concept_relations / concept_mastery / learning_events / resource_interactions

### 新增模块
- memory/ (mastery.py / tracker.py / spaced.py / gaps.py / preferences.py)
- memory Skill (get_mastery / update_mastery / get_preferences / record_event)

### Builder 路径生成升级
- 跳过已掌握 (mastery >= 0.8)
- 优先继续学习中 / 定向补充缺口 / 插入间隔重复复习

---

---

## phase(4): 持续更新引擎 ✓

**日期**: 2026-06-23

### 搜索工具日期过滤
- 所有 5 个搜索源新增 `since_days` 参数: SerpAPI (tbs), Tavily (days), arXiv (submittedDate), YouTube (publishedAfter), GitHub (created:>=)
- 新增 `_since_iso` / `_since_yyyymmdd` / `_since_date` 辅助函数

### 增量采集模式
- Collector 新增 `incremental` + `since_days` state 字段
- 增量模式: 查询已有 URL 集合加入 avoid_set, 自动计算 since_days
- 采集后记录 `crawl_tasks` 表用于追踪上次采集时间

### 全文内容哈希
- `fetch_page` 返回 `content_hash` (sha256 of full text)
- 比原有 collector 的 md5(snippet+title) 更准确

### 变更检测 (updater.py)
- `check_updates()`: 并发 8 路 fetch, 比对 content_hash, 记录 updates 表
- `incremental_collect()`: 对已有项目增量采集新资源
- `apply_updates()`: 增量采集 + 变更检测 + 自动重建站点
- `UpdateReport` 数据类: 统计 new/updated/removed/unchanged/errors

### 定时调度 (scheduler.py)
- `start_scheduler()`: asyncio 定时循环, 读取 openlearning.yaml 配置
- `run_once()`: 单次更新检查
- 支持 daily/weekly/monthly 间隔

### CLI 命令
- `openlearning update check <id>`: 检查变更, 显示报告
- `openlearning update apply <id>`: 增量采集 + 变更检测 + 重建站点
- `openlearning update watch <id>`: 前台定时更新 (Ctrl+C 停止)

### 数据库辅助函数
- `record_update()`: 写入 updates 表
- `get_updates_since()`: 查询指定时间后的变更
- `get_update_summary()`: 聚合统计 (new/updated/removed counts)
- `get_existing_urls()`: 获取项目已有 URL 集合
- `get_last_crawl_date()`: 获取上次采集时间
- `record_crawl_task()`: 记录采集任务

### AgentState 扩展
- 新增 `incremental`, `since_days`, `update_report` 字段

### 测试
- test_updater.py: UpdateReport / check_updates (mock fetch) / date helpers
- test_search_incremental.py: 5 个搜索源的 since_days 参数验证

---

next:

## phase(5): 内容质量 + Supervisor + Memory ✓

**日期**: 2026-06-22

### 内容质量提升
- Analyzer: fetch 全文 + LLM 深度分析 (extract/tag/summarize 并行化)
- Builder: LLM 生成丰富知识点 (定义/详解/要点/实例/误区/建议)
- Builder/Analyzer 并发 3→8, 性能提升 ~5x
- 知识页面 9 个内容区块 + 推荐资源卡片
- 文件名安全处理 (节点 ID 中的路径分隔符)

### Supervisor 动态编排
- 规则路由 → LLM 决策 (achat_json, 回退规则逻辑)
- Graph 重构为中心路由: START → supervisor → [agent] → supervisor → END
- 新增 supervisor_log 决策日志

### Memory 系统接入
- Memory Agent: 调用 memory/gaps.py + preferences 推断
- Planner: 读取 mastery 跳过已掌握, 生成缺口搜索词
- Builder: 记录学习事件到 learning_events 表
- 修复 update_mastery 双事务 bug (合并为单事务)
- SM-2 逻辑去重 (skills/memory → memory/mastery.py)

---

## phase(6): 站点体验升级 ✓

**日期**: 2026-06-22

### Index 页面
- 全节点显示 (去掉 nodes[:20] 限制), 按 importance 排序
- 类型+难度双维度筛选, 类型分布色条
- 搜索修复 (data-id 属性匹配)
- 收藏夹入口

### Graph 页面
- 搜索框高亮匹配节点
- hover tooltip (type/difficulty/definition)
- 浮动图例面板
- 布局切换 (层次/力导向/环形/网格)
- 暗色模式边线修复

### Learning Path 页面
- 使用前置关系 Mermaid 图 (非顺序连接)
- 按难度分阶段折叠 (入门/基础/进阶/高级)
- 进度跟踪 (checkbox + localStorage + 进度条)
- priority=high 标识

### Concept 页面
- 显示 edge 的 reason 和 weight
- 前后翻页导航
- 重要度星级 (node.importance)
- 图谱入口按钮
- 进阶方向修复 (用 prerequisite edges)

### 新增 Bookmarks 页面
- 收藏管理 (查看/移除/清空)
- 空状态引导

---

## phase(7): 导出功能 ✓

**日期**: 2026-06-23

### Markdown 导出 (exporters.py)
- 结构化学习笔记: 目录 / 概念总览 / 详细笔记
- 按难度分组 (入门/基础/进阶)
- 概念详情: 定义 / 详解 / 关键要点 / 示例 / 常见误区 / 学习建议
- 前置知识 / 进阶方向 / 相关概念 (含 edge reason)
- 推荐资源链接
- 学习路径章节 (可选)

### Anki 卡片导出
- 6 种卡片类型: 定义 / 解释摘要 / 关键要点 / 常见误区 / 前置知识 / 进阶方向
- Tab 分隔格式，可直接导入 Anki
- 自动按难度打标签 (beginner/intermediate/advanced)
- deck 头部格式 (#deck:名称)

### CSV 导出
- 概念元数据表格: id / name / type / difficulty / importance
- 前置知识 / 进阶方向列
- 关键要点计数 / 是否有示例

### CLI 更新
- `openlearning export <id> --format markdown` — Markdown 学习笔记
- `openlearning export <id> --format anki` — Anki 卡片
- `openlearning export <id> --format csv` — CSV 表格
- `openlearning export <id> --format json` — 知识图谱 JSON
- 支持 `--output` 自定义输出路径
- 显示导出统计 (卡片数/行数)

### 测试
- test_exporters.py: Markdown 结构 / Anki 格式 / CSV 列 / 辅助函数

---

## phase(8): 中文数据源 + 多项目管理 ✓

**日期**: 2026-06-23

### Bilibili 视频采集器
- `bilibili_search` 工具: 搜索 Bilibili 视频教程
- 使用 Bilibili 搜索 API (免费，无需 API key)
- 返回: url / title / snippet / author / play_count / duration / published
- 支持 `since_days` 时间过滤 (pubtime_begin/pubtime_end)
- HTML 标签自动清理

### 知乎问答采集器
- `zhihu_search` 工具: 搜索知乎问答和专栏文章
- 使用知乎搜索 API (免费，无需 API key)
- 返回: url / title / snippet / author / voteup_count
- 支持 answer 和 article 两种类型
- URL 自动构建 (question/answer 或 zhuanlan)
- 失败时回退到 DuckDuckGo site:zhihu.com

### Collector Agent 集成
- 中文查询路由: web + bilibili + zhihu
- 英文查询路由: web + arXiv + YouTube + GitHub (不变)
- 工具路由器自动识别中文主题，添加 bilibili/zhihu

### 多项目管理
- `openlearning project-update` — 更新标题/描述
- `openlearning project-archive` — 归档项目 (保留数据)
- `openlearning project-activate` — 激活已归档项目
- `openlearning project-delete` — 删除项目 (需确认)
- `openlearning project-compare` — 对比多个项目数据
- `list_projects` 增强: 显示资源数/平均质量/来源分布

### 数据库新增函数
- `update_project()` — 更新项目字段
- `delete_project()` — 级联删除项目及关联数据
- `get_project_stats()` — 项目聚合统计
- `list_projects_with_stats()` — 带统计的项目列表

### 测试
- test_search_cn.py: Bilibili/知乎搜索 (mock HTTP)
- test_project_mgmt.py: 项目 CRUD / 统计 / 归档流程
