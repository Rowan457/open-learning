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

next:
- [ ] Phase 1: MVP 核心采集 + 生成
