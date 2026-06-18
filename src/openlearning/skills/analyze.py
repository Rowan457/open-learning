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
    """
    scores: dict[str, float] = {}

    # 1. Authority (source credibility)
    source = metadata.get("source", "")
    authority_map = {
        "arxiv": 9.0,
        "github": 7.0,
        "youtube": 6.0,
        "google": 5.0,
        "duckduckgo": 4.0,
    }
    scores["authority"] = authority_map.get(source, 5.0)

    # Extra: GitHub stars
    if stars := metadata.get("stars"):
        if stars > 10000:
            scores["authority"] = min(10, scores["authority"] + 2)
        elif stars > 1000:
            scores["authority"] = min(10, scores["authority"] + 1)

    # 2. Content richness
    content_len = len(content)
    code_blocks = content.count("```")
    has_images = "![" in content or "<img" in content

    richness = 3.0
    if content_len > 5000:
        richness = 7.0
    elif content_len > 2000:
        richness = 5.0
    if code_blocks > 3:
        richness = min(10, richness + 1.5)
    if has_images:
        richness = min(10, richness + 0.5)
    scores["richness"] = richness

    # 3. Freshness
    published = metadata.get("published", "")
    if published:
        try:
            pub_date = datetime.strptime(published[:10], "%Y-%m-%d")
            age_days = (datetime.utcnow() - pub_date).days
            if age_days < 180:
                scores["freshness"] = 10.0
            elif age_days < 365:
                scores["freshness"] = 8.0
            elif age_days < 730:
                scores["freshness"] = 6.0
            elif age_days < 1825:
                scores["freshness"] = 4.0
            else:
                scores["freshness"] = 2.0
        except (ValueError, TypeError):
            scores["freshness"] = 5.0
    else:
        scores["freshness"] = 5.0  # unknown

    # 4. Community (stars, comments, etc.)
    scores["community"] = 5.0  # default, enriched by metadata
    if stars := metadata.get("stars"):
        if stars > 5000:
            scores["community"] = 9.0
        elif stars > 1000:
            scores["community"] = 7.0
        elif stars > 100:
            scores["community"] = 6.0

    # 5. Structure quality
    has_headings = "#" in content or "<h" in content
    has_list = "- " in content or "<li" in content
    has_code = "```" in content or "<code" in content

    structure = 4.0
    if has_headings:
        structure += 2.0
    if has_list:
        structure += 1.5
    if has_code:
        structure += 1.5
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


# ── Tools Export ─────────────────────────────────────────────

TOOLS = [score, summarize, tag, extract_knowledge, discover_relations, compare]


def get_tools() -> list:
    return list(TOOLS)
