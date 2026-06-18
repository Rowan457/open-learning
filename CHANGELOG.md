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

next:
- [ ] Phase 1: MVP 核心采集 + 生成
