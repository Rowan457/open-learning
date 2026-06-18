你是 OpenLearning 项目的开发 Agent。请按照以下 Phase 检查点机制管理开发节奏。

## 任务

$ARGUMENTS

## 步骤

### 1. 恢复 Phase 状态

运行 `git log -1 --format="%s"` 获取最新 commit message。

- 无 commit 历史 → 从 Phase 1 开始
- 解析 `phase(N):` 中的 N → 当前应执行 Phase N+1
- 显示进度条：`[■■■□□] Phase 3/5`（总数从 PROJECT_SPECS.md §12 统计）

### 2. 读取当前 Phase 任务

从 PROJECT_SPECS.md §12 开发路线图中，找到当前 Phase 的任务清单，逐一执行。

### 3. 编码执行

按任务清单编码，每完成一个子任务打勾。注意：
- Phase 启动上下文：git log + PROJECT_SPECS.md 相关章节 + 必要源文件（控制在 10-20k tokens）
- 执行中仅保留当前任务相关文件
- 有未提交变更时先提醒

### 4. 完成 Phase 并提交

所有子任务完成后，执行 git checkpoint：

```bash
git add -A
git commit -m "phase(<N>): <phase_title> ✓

<变更摘要，列出新增/修改的文件数和行数>

completed:
- [x] 子任务 1
- [x] 子任务 2

next:
- [ ] Phase N+1 子任务预览"
```

Commit message 必须包含 `phase(N):` 标记，否则状态恢复会失败。

### 5. 安全保障

- `git status` 有未提交变更 → 先提醒用户
- 支持 `git revert` 回滚到任意 Phase
- 每次启动显示当前进度
