"""Analyze Skill — content analysis and knowledge extraction.

Tools: score, summarize, tag, extract_knowledge, discover_relations, compare
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ── Input Schemas ────────────────────────────────────────────

class ScoreInput(BaseModel):
    content: str = Field(description="要评分的内容")
    metadata: dict = Field(default_factory=dict, description="资源元数据(url, title, source等)")


class SummarizeInput(BaseModel):
    content: str = Field(description="要生成摘要的内容")
    lang: str = Field(default="zh", description="输出语言: zh / en")


class TagInput(BaseModel):
    content: str = Field(description="要标注的内容")


class ExtractKnowledgeInput(BaseModel):
    content: str = Field(description="要提取知识的内容")
    existing_concepts: list[str] = Field(default_factory=list, description="已有的概念列表(避免重复)")
    model: str = Field(default="mimo-v2.5", description="使用的模型")


class DiscoverRelationsInput(BaseModel):
    new_concepts: list[dict] = Field(description="新提取的概念列表")
    existing_graph: dict = Field(default_factory=dict, description="已有的知识图谱")
    model: str = Field(default="mimo-v2.5", description="使用的模型")


class CompareInput(BaseModel):
    resource_a: dict = Field(description="资源 A")
    resource_b: dict = Field(description="资源 B")


# ── Rule-Based Scoring ───────────────────────────────────────

def _rule_score(content: str, metadata: dict) -> dict[str, float]:
    """Rule-based quality scoring (zero LLM cost).

    Dimensions: authority, richness, freshness, community, structure.
    权重: authority(25%) + richness(20%) + freshness(20%) + community(15%) + structure(20%)
    """
    scores: dict[str, float] = {}
    source = metadata.get("source", "")

    # ── 1. Authority (来源权威性) ─────────────────────────
    authority_map = {
        "arxiv": 8.0,      # 学术论文，权威
        "github": 7.0,      # 代码仓库，实用
        "youtube": 6.0,     # 视频教程，直观
        "google": 6.0,      # 网页搜索，通用
        "tavily": 6.0,      # AI 优化搜索
        "duckduckgo": 5.0,  # 免费搜索
    }
    scores["authority"] = authority_map.get(source, 5.0)

    # GitHub stars 加成
    if stars := metadata.get("stars"):
        if stars > 5000:
            scores["authority"] = min(10, scores["authority"] + 2.0)
        elif stars > 1000:
            scores["authority"] = min(10, scores["authority"] + 1.5)
        elif stars > 100:
            scores["authority"] = min(10, scores["authority"] + 1.0)

    # ── 2. Content Richness (内容丰富度) ─────────────────
    content_len = len(content)
    code_blocks = content.count("```")
    has_images = "![" in content or "<img" in content

    # 基础分：根据内容长度
    if content_len > 3000:
        richness = 7.0
    elif content_len > 1500:
        richness = 6.0
    elif content_len > 500:
        richness = 5.0
    else:
        richness = 4.0  # 短内容也能接受

    # 加成
    if code_blocks > 0:
        richness = min(10, richness + 1.5)  # 有代码块
    if has_images:
        richness = min(10, richness + 0.5)  # 有图片
    scores["richness"] = richness

    # ── 3. Freshness (时效性) ────────────────────────────
    published = metadata.get("published", "")
    if published:
        try:
            pub_date = datetime.strptime(published[:10], "%Y-%m-%d")
            age_days = (datetime.utcnow() - pub_date).days
            if age_days < 180:
                scores["freshness"] = 9.0   # 6 个月内
            elif age_days < 365:
                scores["freshness"] = 7.0   # 1 年内
            elif age_days < 730:
                scores["freshness"] = 5.0   # 2 年内
            elif age_days < 1825:
                scores["freshness"] = 3.0   # 5 年内
            else:
                scores["freshness"] = 2.0   # 超过 5 年
        except (ValueError, TypeError):
            scores["freshness"] = 6.0  # 解析失败，给中等分
    else:
        scores["freshness"] = 6.0  # 无日期，假设较新（避免过度惩罚）

    # ── 4. Community (社区认可) ──────────────────────────
    scores["community"] = 5.0  # 默认
    if stars := metadata.get("stars"):
        if stars > 5000:
            scores["community"] = 9.0
        elif stars > 1000:
            scores["community"] = 7.0
        elif stars > 100:
            scores["community"] = 6.0

    # ── 5. Structure (结构质量) ─────────────────────────
    has_headings = "#" in content or "<h" in content
    has_list = "- " in content or "<li" in content or "* " in content
    has_code = "```" in content or "<code" in content
    has_links = "http" in content

    structure = 4.0  # 基础分
    if has_headings:
        structure += 2.0
    if has_list:
        structure += 1.0
    if has_code:
        structure += 1.5
    if has_links:
        structure += 0.5
    scores["structure"] = min(10, structure)

    return scores


@tool("score", args_schema=ScoreInput)
async def score(content: str, metadata: dict | None = None) -> dict[str, Any]:
    """多维度质量评分（规则引擎，零 LLM 成本）。

    评估维度: 来源权威性、内容丰富度、时效性、社区认可、结构质量。
    返回 {scores: {dim: score}, final_score, reasoning}。
    """
    meta = metadata or {}
    scores = _rule_score(content, meta)

    # Weighted average
    weights = {
        "authority": 0.30,
        "richness": 0.25,
        "freshness": 0.20,
        "community": 0.15,
        "structure": 0.10,
    }
    final_score = sum(scores[dim] * w for dim, w in weights.items())

    # Freshness multiplier
    published = meta.get("published", "")
    if published:
        try:
            pub_date = datetime.strptime(published[:10], "%Y-%m-%d")
            age_days = (datetime.utcnow() - pub_date).days
            if age_days < 180:
                multiplier = 1.0
            elif age_days < 730:
                multiplier = 0.85
            elif age_days < 1825:
                multiplier = 0.7
            else:
                multiplier = 0.5
            final_score *= multiplier
        except (ValueError, TypeError):
            pass

    return {
        "scores": scores,
        "final_score": round(final_score, 2),
        "reasoning": f"Authority={scores['authority']:.1f}, Richness={scores['richness']:.1f}, "
        f"Freshness={scores['freshness']:.1f}, Community={scores['community']:.1f}, "
        f"Structure={scores['structure']:.1f}",
    }


# ── Summarize ────────────────────────────────────────────────

@tool("summarize", args_schema=SummarizeInput)
async def summarize(content: str, lang: str = "zh") -> dict[str, Any]:
    """生成摘要（规则提取，零 LLM 成本）。

    提取前几段和关键句子作为摘要。
    返回 {summary, key_points}。
    """
    lines = content.split("\n")
    # Take first non-empty lines as summary
    summary_lines = []
    for line in lines:
        line = line.strip()
        if line and len(line) > 20:
            summary_lines.append(line)
        if len(summary_lines) >= 5:
            break

    summary = " ".join(summary_lines)[:500]

    # Extract key points (lines starting with bullet markers)
    key_points = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "• ", "1.", "2.", "3.")):
            key_points.append(stripped.lstrip("-*•0123456789. "))
        if len(key_points) >= 5:
            break

    return {
        "summary": summary,
        "key_points": key_points,
    }


# ── Tag ──────────────────────────────────────────────────────

@tool("tag", args_schema=TagInput)
async def tag(content: str) -> dict[str, Any]:
    """智能标注（规则，零 LLM 成本）。

    自动标注: 难度、类型、包含的概念关键词。
    返回 {difficulty, type, concepts}。
    """
    content_lower = content.lower()

    # Difficulty detection
    beginner_signals = ["入门", "初学", "beginner", "introduction", "getting started", "基础"]
    advanced_signals = ["深入", "高级", "advanced", "internals", "architecture", "优化", "性能"]

    beginner_count = sum(1 for s in beginner_signals if s in content_lower)
    advanced_count = sum(1 for s in advanced_signals if s in content_lower)

    if beginner_count > advanced_count:
        difficulty = "beginner"
    elif advanced_count > beginner_count:
        difficulty = "advanced"
    else:
        difficulty = "intermediate"

    # Content type detection
    content_type = "article"
    if "youtube.com" in content_lower or "video" in content_lower:
        content_type = "video"
    elif "arxiv.org" in content_lower or "abstract" in content_lower:
        content_type = "paper"
    elif "github.com" in content_lower or "```" in content:
        content_type = "repo"
    elif "course" in content_lower or "课程" in content:
        content_type = "course"

    # Concept keywords extraction (simple frequency-based)
    import re

    # Look for capitalized multi-word terms and technical terms
    patterns = [
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b",  # CamelCase words
        r"`([^`]+)`",  # backtick-quoted terms
        r"\*\*([^*]+)\*\*",  # bold terms
    ]
    concepts = set()
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for m in matches:
            if 3 < len(m) < 50:
                concepts.add(m.strip())

    return {
        "difficulty": difficulty,
        "type": content_type,
        "concepts": list(concepts)[:20],
    }


# ── Extract Knowledge ────────────────────────────────────────

@tool("extract_knowledge", args_schema=ExtractKnowledgeInput)
async def extract_knowledge(
    content: str,
    existing_concepts: list[str] | None = None,
    model: str = "mimo-v2.5",
) -> dict[str, Any]:
    """从内容中提取知识概念（规则提取，零 LLM 成本）。

    提取: 概念名称、定义、类型、难度。
    返回 {concepts: [{name, type, definition, difficulty}]}。
    """
    existing = set(c.lower() for c in (existing_concepts or []))
    concepts = []

    import re

    # Strategy 1: Extract heading-defined concepts
    lines = content.split("\n")
    for i, line in enumerate(lines):
        # Markdown headings
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            heading = line.lstrip("#").strip()
            if 2 <= len(heading) <= 80 and heading.lower() not in existing:
                # Look for definition in next few lines
                definition = ""
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("#"):
                        definition = lines[j].strip()[:200]
                        break

                concepts.append({
                    "name": heading,
                    "type": "concept",
                    "definition": definition,
                    "difficulty": "intermediate",
                })
                existing.add(heading.lower())

    # Strategy 2: Extract bold-defined terms
    bold_pattern = r"\*\*([^*]+)\*\*[:\s—–-]+([^\n]+)"
    for match in re.finditer(bold_pattern, content):
        name = match.group(1).strip()
        definition = match.group(2).strip()[:200]
        if 2 < len(name) < 60 and name.lower() not in existing:
            concepts.append({
                "name": name,
                "type": "concept",
                "definition": definition,
                "difficulty": "intermediate",
            })
            existing.add(name.lower())

    return {"concepts": concepts[:30]}


# ── Discover Relations ───────────────────────────────────────

@tool("discover_relations", args_schema=DiscoverRelationsInput)
async def discover_relations(
    new_concepts: list[dict],
    existing_graph: dict | None = None,
    model: str = "mimo-v2.5",
) -> list[dict[str, Any]]:
    """发现概念间的关系（规则推断，零 LLM 成本）。

    基于位置、共现、关键词推断: prerequisite / extends / related。
    返回 [{from, to, type, weight, reason}]。
    """
    graph = existing_graph or {}
    relations = []

    existing_names = set()
    if nodes := graph.get("nodes"):
        for node in nodes:
            existing_names.add(node.get("name", "").lower())

    for i, c1 in enumerate(new_concepts):
        name1 = c1.get("name", "").lower()
        for j, c2 in enumerate(new_concepts):
            if i >= j:
                continue
            name2 = c2.get("name", "").lower()

            # Co-occurrence based relation (same extraction context)
            relations.append({
                "from": name1.replace(" ", "_"),
                "to": name2.replace(" ", "_"),
                "type": "related",
                "weight": 0.5,
                "reason": "Co-occur in the same resource",
            })

    # Connect new concepts to existing graph (related only)
    for c in new_concepts:
        name = c.get("name", "").lower()
        for existing in list(existing_names)[:5]:
            # Simple substring match
            if name in existing or existing in name:
                relations.append({
                    "from": name.replace(" ", "_"),
                    "to": existing.replace(" ", "_"),
                    "type": "related",
                    "weight": 0.7,
                    "reason": "Name similarity",
                })

    return relations


# ── Compare ──────────────────────────────────────────────────

@tool("compare", args_schema=CompareInput)
async def compare(resource_a: dict, resource_b: dict) -> dict[str, Any]:
    """对比两个资源的差异。

    返回 {differences: [], recommendation}。
    """
    diffs = []

    # Compare quality scores
    score_a = resource_a.get("quality_score", 0)
    score_b = resource_b.get("quality_score", 0)
    if abs(score_a - score_b) > 1:
        diffs.append({
            "dimension": "quality",
            "a": score_a,
            "b": score_b,
            "better": "a" if score_a > score_b else "b",
        })

    # Compare types
    type_a = resource_a.get("resource_type", "")
    type_b = resource_b.get("resource_type", "")
    if type_a != type_b:
        diffs.append({
            "dimension": "type",
            "a": type_a,
            "b": type_b,
        })

    # Compare difficulty
    diff_a = resource_a.get("difficulty", "")
    diff_b = resource_b.get("difficulty", "")
    if diff_a != diff_b:
        diffs.append({
            "dimension": "difficulty",
            "a": diff_a,
            "b": diff_b,
        })

    recommendation = "a" if score_a >= score_b else "b"
    return {
        "differences": diffs,
        "recommendation": recommendation,
    }


# ── LLM Deep Analysis (Phase 2) ─────────────────────────────

class LLMSummarizeInput(BaseModel):
    content: str = Field(description="要摘要的内容")
    lang: str = Field(default="zh", description="输出语言: zh / en")
    max_length: int = Field(default=300, description="摘要最大长度")


class LLMExtractInput(BaseModel):
    content: str = Field(description="要提取知识的内容")
    existing_concepts: list[str] = Field(default_factory=list, description="已有概念（避免重复）")


class LLMDifficultyInput(BaseModel):
    content: str = Field(description="要判断难度的内容")
    title: str = Field(default="", description="资源标题")


class MultiDimScoreInput(BaseModel):
    content: str = Field(description="要评分的内容")
    metadata: dict = Field(default_factory=dict, description="资源元数据")


class DetectDuplicatesInput(BaseModel):
    resources: list[dict] = Field(description="资源列表")
    threshold: float = Field(default=0.8, description="相似度阈值 0-1")


@tool("llm_summarize", args_schema=LLMSummarizeInput)
async def llm_summarize(content: str, lang: str = "zh", max_length: int = 300) -> dict[str, Any]:
    """LLM 智能摘要：提取核心观点和关键信息。

    返回 {summary, key_points, one_line_summary}。
    """
    from openlearning.llm import achat_json

    prompt = f"""请对以下内容生成结构化摘要。

要求：
1. 一句话摘要（{max_length} 字以内）
2. 3-5 个关键要点
3. 输出语言：{'中文' if lang == 'zh' else 'English'}

内容：
{content[:4000]}

请以 JSON 格式输出：
{{
  "summary": "完整摘要",
  "one_line_summary": "一句话摘要",
  "key_points": ["要点1", "要点2", "要点3"]
}}"""

    try:
        result = await achat_json(
            messages=[{"role": "user", "content": prompt}],
            tier="lite",
            temperature=0.2,
        )
        return result
    except Exception:
        # Fallback to rule-based
        return await summarize.ainvoke({"content": content, "lang": lang})


@tool("llm_extract_knowledge", args_schema=LLMExtractInput)
async def llm_extract_knowledge(
    content: str,
    existing_concepts: list[str] | None = None,
) -> dict[str, Any]:
    """LLM 知识提取：从内容中提取概念、定义、技术、最佳实践。

    返回 {concepts: [{name, type, definition, difficulty, importance}]}。
    """
    from openlearning.llm import achat_json

    existing = existing_concepts or []
    existing_str = ", ".join(existing[:20]) if existing else "无"

    prompt = f"""从以下内容中提取知识概念。

已有概念（避免重复）：{existing_str}

内容：
{content[:4000]}

请提取所有有价值的概念，以 JSON 格式输出：
{{
  "concepts": [
    {{
      "name": "概念名称",
      "type": "concept/principle/technology/practice",
      "definition": "简明定义",
      "difficulty": "beginner/intermediate/advanced",
      "importance": 0.0-1.0
    }}
  ]
}}"""

    try:
        result = await achat_json(
            messages=[{"role": "user", "content": prompt}],
            tier="standard",
            temperature=0.1,
        )
        return result
    except Exception:
        # Fallback to rule-based
        return await extract_knowledge.ainvoke({
            "content": content,
            "existing_concepts": existing_concepts or [],
        })


@tool("llm_tag", args_schema=LLMDifficultyInput)
async def llm_tag(content: str, title: str = "") -> dict[str, Any]:
    """LLM 难度标注：智能判断内容难度和适合的学习阶段。

    返回 {difficulty, prerequisites, learning_stage, topics}。
    """
    from openlearning.llm import achat_json

    prompt = f"""分析以下学习资源的难度和适合的学习阶段。

标题：{title}
内容：
{content[:3000]}

请以 JSON 格式输出：
{{
  "difficulty": "beginner/intermediate/advanced",
  "prerequisites": ["前置知识1", "前置知识2"],
  "learning_stage": "入门/进阶/深入",
  "topics": ["主题1", "主题2", "主题3"],
  "reasoning": "判断理由"
}}"""

    try:
        result = await achat_json(
            messages=[{"role": "user", "content": prompt}],
            tier="lite",
            temperature=0.1,
        )
        return result
    except Exception:
        # Fallback to rule-based
        return await tag.ainvoke({"content": content})


@tool("multi_dim_score", args_schema=MultiDimScoreInput)
async def multi_dim_score(content: str, metadata: dict | None = None) -> dict[str, Any]:
    """多维度质量评分：规则 + LLM 混合评分。

    规则维度（零成本）：authority, freshness, structure
    LLM 维度：content_depth, teaching_quality, practicality

    返回 {scores: {dim: score}, final_score, reasoning}。
    """
    from openlearning.llm import achat_json

    meta = metadata or {}

    # Rule-based dimensions (zero cost)
    rule_scores = _rule_score(content, meta)

    # LLM dimensions
    prompt = f"""评估以下学习资源的质量（每项 0-10 分）。

内容：
{content[:3000]}

请以 JSON 格式输出评分：
{{
  "content_depth": {{"score": 0-10, "reason": "理由"}},
  "teaching_quality": {{"score": 0-10, "reason": "理由"}},
  "practicality": {{"score": 0-10, "reason": "理由"}}
}}

评分标准：
- content_depth: 内容深度，是否深入讲解而非浅尝辄止
- teaching_quality: 教学质量，是否有清晰结构、示例、练习
- practicality: 实操性，是否有可运行代码、动手练习"""

    try:
        llm_result = await achat_json(
            messages=[{"role": "user", "content": prompt}],
            tier="standard",
            temperature=0.2,
        )

        # Merge rule + LLM scores
        all_scores = {
            "authority": rule_scores["scores"]["authority"],
            "richness": rule_scores["scores"]["richness"],
            "freshness": rule_scores["scores"]["freshness"],
            "community": rule_scores["scores"]["community"],
            "structure": rule_scores["scores"]["structure"],
            "content_depth": llm_result.get("content_depth", {}).get("score", 5.0),
            "teaching_quality": llm_result.get("teaching_quality", {}).get("score", 5.0),
            "practicality": llm_result.get("practicality", {}).get("score", 5.0),
        }

        # Weighted average
        weights = {
            "authority": 0.15,
            "richness": 0.10,
            "freshness": 0.10,
            "community": 0.05,
            "structure": 0.10,
            "content_depth": 0.25,
            "teaching_quality": 0.15,
            "practicality": 0.10,
        }
        final_score = sum(all_scores[dim] * w for dim, w in weights.items())

        return {
            "scores": all_scores,
            "final_score": round(final_score, 2),
            "method": "hybrid",
            "llm_reasoning": llm_result,
        }

    except Exception:
        # Fallback to rule-only
        return {
            "scores": rule_scores["scores"],
            "final_score": rule_scores["final_score"],
            "method": "rule_only",
            "reasoning": rule_scores["reasoning"],
        }


@tool("detect_duplicates", args_schema=DetectDuplicatesInput)
async def detect_duplicates(resources: list[dict], threshold: float = 0.8) -> dict[str, Any]:
    """去重 & 相似度检测：基于标题和内容指纹识别重复资源。

    返回 {unique: [...], duplicates: [...], stats: {...}}。
    """
    import hashlib
    from difflib import SequenceMatcher

    unique = []
    duplicates = []
    seen_hashes: dict[str, int] = {}  # hash → index in unique
    seen_titles: list[tuple[str, int]] = []  # (normalized_title, index)

    for r in resources:
        url = r.get("url", "")
        title = r.get("title", "").strip().lower()
        snippet = r.get("snippet", "")

        # Hash-based dedup (exact content match)
        content_hash = hashlib.md5(f"{title}|{snippet[:200]}".encode()).hexdigest()
        if content_hash in seen_hashes:
            duplicates.append({
                "resource": r,
                "reason": "exact_content_match",
                "duplicate_of": unique[seen_hashes[content_hash]].get("url", ""),
            })
            continue

        # URL-based dedup
        url_normalized = url.rstrip("/").split("?")[0].split("#")[0].lower()
        if any(u == url_normalized for u, _ in seen_titles):
            duplicates.append({
                "resource": r,
                "reason": "duplicate_url",
            })
            continue

        # Title similarity dedup
        is_similar = False
        for seen_title, idx in seen_titles:
            similarity = SequenceMatcher(None, title, seen_title).ratio()
            if similarity >= threshold:
                duplicates.append({
                    "resource": r,
                    "reason": "similar_title",
                    "similarity": round(similarity, 2),
                    "duplicate_of": unique[idx].get("url", ""),
                })
                is_similar = True
                break

        if not is_similar:
            seen_hashes[content_hash] = len(unique)
            seen_titles.append((title, len(unique)))
            unique.append(r)

    return {
        "unique": unique,
        "duplicates": duplicates,
        "stats": {
            "total": len(resources),
            "unique": len(unique),
            "duplicates": len(duplicates),
            "dedup_rate": round(len(duplicates) / max(len(resources), 1), 2),
        },
    }


# ── Tools Export ─────────────────────────────────────────────

TOOLS = [
    score, summarize, tag, extract_knowledge, discover_relations, compare,
    llm_summarize, llm_extract_knowledge, llm_tag, multi_dim_score, detect_duplicates,
]


def get_tools() -> list:
    return list(TOOLS)
