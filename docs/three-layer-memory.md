# 从零到一：如何用三层记忆系统让 AI Agent 越用越懂你

> 🧠 本文详细介绍 OpenLearning 的三层记忆架构设计，涵盖项目记忆、偏好记忆、学习记忆的实现方案，以及如何通过知识缺口分析驱动个性化学习路径生成。

## 📖 前言

在构建 AI Agent 时，一个常见的痛点是：**Agent 每次对话都是从零开始**。用户说"我想学 Rust"，Agent 采集资源、生成知识图谱、输出学习路径——然后下次再说"我想学 Rust"，它又从头来一遍。

为什么会这样？因为大多数 Agent 没有**记忆**。

OpenLearning 的解决方案是：**三层记忆系统**。它让 Agent 记住你是谁、你喜欢什么、你已经学会了什么，从而实现"越用越懂你"的效果。

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户输入                               │
│                  "我想学 Rust"                            │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Memory Agent（记忆查询）                     │
│                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │  项目记忆    │ │  偏好记忆    │ │  学习记忆    │       │
│  │             │ │             │ │             │       │
│  │ · 历史项目  │ │ · 资源类型  │ │ · 已掌握    │       │
│  │ · 已推荐URL │ │ · 语言偏好  │ │ · 学习中    │       │
│  │ · 相似项目  │ │ · 难度偏好  │ │ · 知识缺口  │       │
│  │             │ │ · 学习风格  │ │ · 待复习    │       │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘       │
│         │               │               │               │
│         └───────────────┼───────────────┘               │
│                         │                               │
│                         ▼                               │
│                  user_memory 输出                        │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              下游 Agent 消费记忆                          │
│                                                         │
│  Planner: 跳过已掌握概念 → 生成缺口搜索词                │
│  Builder: 个性化学习路径 → 跳过已掌握 → 优先复习         │
│  Graph:   注入研究简报 → 告诉 Supervisor 用户背景        │
└─────────────────────────────────────────────────────────┘
```

三层记忆各司其职，通过 `user_memory` 字典统一输出，供下游 Agent 消费。

## 🗂️ 第一层：项目记忆

### 职责

记录用户的历史项目和已推荐资源，避免重复推荐。

### 实现

```python
async def _query_project_history(user_id: str) -> list[dict]:
    """查询用户最近的项目。"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT * FROM projects WHERE status = 'active' "
            "ORDER BY updated_at DESC LIMIT 10"
        ))
        return [dict(zip(result.keys(), row)) for row in result.fetchall()]

async def _query_avoid_list(user_id: str) -> list[str]:
    """获取已推荐的 URL 列表，避免跨项目重复。"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT url FROM resources"))
        return [row[0] for row in result.fetchall()]
```

### 数据流

```
projects 表 → 最近 10 个项目 → 相似项目匹配
resources 表 → 所有已推荐 URL → avoid_list（去重用）
```

### 关键设计

**avoid_list 的作用**：当用户说"我想学 Rust"时，系统会检查之前是否推荐过相同的 URL。如果某个 Rust 教程在之前的项目中已经推荐过，这次就不会重复推荐。

**相似项目匹配**：简单的子串匹配，用于快速找到相关历史项目。如果用户之前学过"Rust 入门"，现在说"Rust 进阶"，系统知道这两个项目相关。

## 🎯 第二层：偏好记忆

### 职责

从用户的历史交互中推断偏好，指导资源筛选和内容生成。

### 实现

偏好记忆分两步：**显式偏好** + **隐式推断**。

```python
async def _learn_preferences(user_id: str) -> dict:
    """学习用户偏好：显式设置 + 隐式推断。"""
    # 第一步：获取显式偏好（用户手动设置的）
    prefs = await get_preferences.ainvoke({"user_id": user_id})

    # 第二步：从交互数据推断隐式偏好
    interactions = _query_interactions(user_id)  # 最近 50 次交互
    if interactions:
        inferred = infer_preferences(interactions)
        # 隐式推断覆盖显式默认值
        for key in ("difficulty", "learning_style"):
            if inferred.get(key) and inferred[key] != prefs.get(key):
                prefs[key] = inferred[key]

    return prefs
```

### 偏好推断算法

```python
# memory/preferences.py

def infer_preferences(interactions: list[dict]) -> dict:
    """从交互数据推断偏好。"""
    # 难度偏好：统计用户查看的资源难度分布
    difficulties = [i.get("difficulty") for i in interactions if i.get("difficulty")]
    if difficulties:
        # 取出现频率最高的难度
        difficulty = Counter(difficulties).most_common(1)[0][0]
    else:
        difficulty = "intermediate"

    # 学习风格：统计用户偏好的资源类型
    # 看视频多 → "visual"，读文章多 → "reading"，写代码多 → "hands-on"
    style = _infer_learning_style(interactions)

    return {"difficulty": difficulty, "learning_style": style}
```

### 偏好字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `difficulty` | string | 难度偏好 | `"beginner"` / `"intermediate"` / `"advanced"` |
| `learning_style` | string | 学习风格 | `"reading"` / `"visual"` / `"hands-on"` |
| `language` | dict | 语言偏好 | `{"zh": 0.7, "en": 0.3}` |
| `resource_type` | dict | 资源类型偏好 | `{"article": 0.5, "video": 0.3, "paper": 0.2}` |

### 下游消费

- **Planner**：根据语言偏好生成中英文搜索词
- **Builder**：根据难度偏好调整学习路径的起点
- **Worker**：根据资源类型偏好优先搜索对应来源

## 📊 第三层：学习记忆

### 职责

追踪用户对每个知识点的掌握程度，识别知识缺口，驱动个性化学习路径。

### 实现

```python
async def _query_mastery(user_id: str) -> dict:
    """查询概念掌握数据。"""
    mastery_list = await get_mastery.ainvoke({"user_id": user_id})

    return {
        "mastered": [m for m in mastery_list if m.get("mastery", 0) >= 0.8],
        "learning": [m for m in mastery_list if 0.2 <= m.get("mastery", 0) < 0.8],
        "not_started": [m for m in mastery_list if m.get("mastery", 0) < 0.2],
        "due_reviews": [m for m in mastery_list if m.get("next_review")],
    }
```

### 掌握度计算

掌握度是一个 0~1 的浮点数，由多个维度加权计算：

```python
# memory/mastery.py

def calculate_mastery(concept_id: str, user_id: str) -> float:
    """多维度掌握度计算。"""
    # 维度权重
    weights = {
        "resource_completion": 0.3,  # 资源完成率
        "quiz_score": 0.25,          # 测验得分
        "time_spent": 0.15,          # 学习时长
        "recency": 0.15,             # 最近活跃度
        "review_count": 0.10,        # 复习次数
        "self_report": 0.05,         # 用户自评
    }

    score = 0.0
    for dim, weight in weights.items():
        dim_score = _get_dimension_score(concept_id, user_id, dim)
        score += dim_score * weight

    return min(1.0, max(0.0, score))
```

### 掌握度分层

```
mastery >= 0.8  →  mastered（已掌握）    →  跳过，不重复学习
0.2 <= mastery < 0.8  →  learning（学习中）  →  继续，优先安排
mastery < 0.2  →  not_started（未开始）  →  正常安排
next_review 非空  →  due_reviews（待复习）  →  插入复习步骤
```

### 知识缺口分析

```python
# memory/gaps.py

def analyze_knowledge_gaps(graph: dict, mastery_list: list[dict]) -> list[dict]:
    """对比知识图谱 vs 掌握数据，找出缺口。"""
    nodes = graph.get("nodes", [])
    mastery_map = {m["concept_id"]: m.get("mastery", 0) for m in mastery_list}

    gaps = []
    for node in nodes:
        concept_id = node.get("id", "")
        mastery = mastery_map.get(concept_id, 0)
        importance = node.get("importance", 0.5)

        # 优先级 = 重要度 × (1 - 掌握度)
        priority = importance * (1 - mastery)

        if mastery < 0.8:  # 未完全掌握
            gaps.append({
                "concept_id": concept_id,
                "name": node.get("name", ""),
                "mastery": mastery,
                "importance": importance,
                "priority": priority,
            })

    # 按优先级排序：重要且不熟练的排前面
    gaps.sort(key=lambda x: x["priority"], reverse=True)
    return gaps
```

### 缺口驱动的搜索词生成

```python
# agents/planner.py

def _generate_gap_queries(gaps: list, analysis: dict) -> list[str]:
    """为知识缺口生成针对性搜索词。"""
    queries = []
    topic = analysis.get("topic", "")

    for gap in gaps[:5]:  # Top 5 缺口
        name = gap.get("name", gap.get("concept_id", ""))
        # 生成针对性搜索词
        queries.append(f"{name} tutorial explained")
        queries.append(f"{name} 教程 详解")

    return queries
```

## 🔗 记忆如何影响决策

### 对 Planner 的影响

```python
# agents/planner.py

def _generate_search_queries(graph, analysis, profile, user_memory):
    queries = []

    # 记忆感知：跳过已掌握概念
    if user_memory:
        mastered_ids = {
            m.get("concept_id", "")
            for m in user_memory.get("mastery", {}).get("mastered", [])
        }
        if mastered_ids:
            # 过滤掉已掌握的子主题
            subtopics = [s for s in subtopics
                        if not any(mid in s.lower() for mid in mastered_ids)]

    # 缺口补充：为未覆盖概念生成搜索词
    gaps = user_memory.get("gaps", [])
    if gaps:
        gap_queries = _generate_gap_queries(gaps, analysis)
        queries.extend(gap_queries)

    return queries
```

### 对 Builder 的影响

```python
# agents/builder.py

def _generate_learning_path(graph, memory):
    mastery = memory.get("mastery", {})
    mastered_ids = {m.get("concept_id", "") for m in mastery.get("mastered", [])}
    learning_ids = {m.get("concept_id", "") for m in mastery.get("learning", [])}

    for concept_id in topo_order:
        if concept_id in mastered_ids:
            continue  # 跳过已掌握
        elif concept_id in learning_ids:
            steps.append({"concept": concept_id, "action": "continue", "priority": "high"})
        else:
            steps.append({"concept": concept_id, "action": "learn", "priority": "normal"})

    # 插入待复习步骤
    for review in mastery.get("due_reviews", [])[:3]:
        steps.insert(0, {"concept": review["concept_id"], "action": "review", "priority": "high"})
```

### 对 Supervisor 的影响

记忆数据被格式化后注入到 Supervisor 的初始化 prompt 中：

```python
# agents/prompts.py

def format_user_preferences(user_memory: dict) -> str:
    parts = []
    prefs = user_memory.get("preferences", {})
    if prefs:
        parts.append(f"偏好难度: {prefs.get('difficulty', '未设置')}")
        parts.append(f"学习风格: {prefs.get('learning_style', '未设置')}")

    mastery = user_memory.get("mastery", {})
    if mastery.get("mastered"):
        parts.append(f"已掌握: {len(mastery['mastered'])} 个概念")

    gaps = user_memory.get("gaps", [])
    if gaps:
        gap_names = [g.get("name", "") for g in gaps[:3]]
        parts.append(f"知识缺口: {', '.join(gap_names)}")

    return "\n".join(parts)
```

## 📁 文件结构

```
src/openlearning/
├── agents/
│   ├── memory.py          # Memory Agent（三层记忆查询入口）
│   └── planner.py         # Planner（消费记忆生成搜索词）
├── tools/
│   └── memory.py          # 记忆工具（get_mastery, get_preferences, record_event）
├── memory/
│   ├── gaps.py            # 知识缺口分析
│   ├── mastery.py         # 掌握度计算 + SM-2 复习调度
│   └── preferences.py     # 偏好推断
└── models.py              # ConceptMastery, LearningEvent 数据模型
```

## 💡 设计思考

### 为什么分三层？

| 层 | 生命周期 | 更新频率 | 作用域 |
|---|---------|---------|-------|
| 项目记忆 | 永久 | 每次采集 | 跨项目 |
| 偏好记忆 | 长期 | 交互时推断 | 全局 |
| 学习记忆 | 永久 | 学习事件触发 | 按概念 |

三层独立演化，互不干扰。用户可以同时学多个领域，每个领域的掌握度独立追踪。

### 为什么用规则而非 LLM？

记忆查询是**高频操作**，每次采集都会触发。如果用 LLM 做记忆查询：
- 增加延迟（每次 +2-5s）
- 增加成本（每次 +$0.01-0.05）
- 结果不稳定（LLM 可能给出不同的掌握度评估）

规则引擎的优势：
- **确定性**：相同输入 always 相同输出
- **零成本**：纯 Python 计算
- **可解释**：掌握度 = 0.73，因为资源完成率 0.8 × 0.3 + 测验 0.6 × 0.25 + ...

### 掌握度为什么不直接用测验分数？

单一维度容易失真：
- 用户快速浏览完所有资源 → 资源完成率 100%，但什么都没记住
- 用户做了一次测验全对 → 测验 100%，但可能是运气

多维度加权更稳健：
- 资源完成率反映投入度
- 测验得分反映理解度
- 学习时长反映深度
- 最近活跃度反映记忆衰减
- 复习次数反映巩固程度

## 🚀 未来优化

1. **向量记忆**：用 embedding 存储用户学习历史，支持语义相似度匹配
2. **遗忘曲线**：基于 Ebbinghaus 遗忘曲线优化复习调度
3. **跨项目迁移**：学过 Rust 的所有权概念，学 C++ 时自动跳过类似概念
4. **记忆衰减**：长期不活跃的概念自动降低掌握度

## 📝 总结

三层记忆系统的核心思路：

1. **项目记忆**解决"不重复"——记住推荐过什么
2. **偏好记忆**解决"对味"——记住用户喜欢什么
3. **学习记忆**解决"个性化"——记住用户会什么

三者协同，让 Agent 从"通用工具"变成"私人教练"。

---

> 💬 如果你也在构建有记忆能力的 Agent，欢迎在评论区交流你的设计方案。
