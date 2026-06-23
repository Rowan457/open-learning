"""Exporters — Markdown notes & Anki cards from knowledge graph data.

Provides structured learning exports:
- Markdown: complete learning notes with concepts, paths, resources
- Anki: spaced-repetition cards (cloze, basic Q&A, relationship)
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


# ── Markdown Export ─────────────────────────────────────────


def export_markdown(
    knowledge_graph: dict,
    learning_path: dict | None = None,
    knowledge_resources: dict[str, list[dict]] | None = None,
    project_title: str = "Learning Notes",
) -> str:
    """Export knowledge graph as structured Markdown learning notes.

    Args:
        knowledge_graph: {nodes: [...], edges: [...]}
        learning_path: {phases: [...]} optional learning path
        knowledge_resources: {concept_id: [resource, ...]} optional resource mapping
        project_title: title for the document

    Returns:
        Complete Markdown string.
    """
    nodes = knowledge_graph.get("nodes", [])
    edges = knowledge_graph.get("edges", [])
    res_map = knowledge_resources or {}

    # Sort by importance desc
    sorted_nodes = sorted(nodes, key=lambda n: n.get("importance", 0.5), reverse=True)

    # Build edge index
    edge_index: dict[str, list[dict]] = {}
    for e in edges:
        for cid in (e.get("from"), e.get("to")):
            edge_index.setdefault(cid, []).append(e)

    lines: list[str] = []

    # Header
    lines.append(f"# {project_title}")
    lines.append("")
    lines.append(f"> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                 f"{len(nodes)} 个概念, {len(edges)} 条关系")
    lines.append("")

    # Table of contents
    lines.append("## 目录")
    lines.append("")
    for i, node in enumerate(sorted_nodes, 1):
        name = node.get("name", node.get("id", ""))
        anchor = _md_anchor(name)
        lines.append(f"{i}. [{name}](#{anchor})")
    lines.append("")

    # Learning path section
    if learning_path and learning_path.get("phases"):
        lines.append("## 学习路径")
        lines.append("")
        for phase in learning_path.get("phases", []):
            phase_name = phase.get("name", "")
            phase_diff = phase.get("difficulty", "")
            label = f"{phase_name}"
            if phase_diff:
                label += f" ({phase_diff})"
            lines.append(f"### {label}")
            lines.append("")
            for cid in phase.get("concept_ids", []):
                cnode = _find_node(nodes, cid)
                if cnode:
                    lines.append(f"- {cnode.get('name', cid)}")
            lines.append("")

    # Difficulty grouping
    lines.append("## 概念总览")
    lines.append("")

    by_diff: dict[str, list[dict]] = {}
    for n in sorted_nodes:
        d = n.get("difficulty", "未分类")
        by_diff.setdefault(d, []).append(n)

    diff_labels = {
        "beginner": "🟢 入门",
        "intermediate": "🟡 基础",
        "advanced": "🔴 进阶",
    }
    for diff_key in ("beginner", "intermediate", "advanced"):
        group = by_diff.pop(diff_key, [])
        if not group:
            continue
        lines.append(f"### {diff_labels.get(diff_key, diff_key)}")
        lines.append("")
        for n in group:
            stars = _importance_stars(n.get("importance", 0.5))
            lines.append(f"- **{n.get('name', '')}** {stars}")
        lines.append("")

    # Remaining difficulty groups
    for diff_key, group in by_diff.items():
        lines.append(f"### {diff_key}")
        lines.append("")
        for n in group:
            stars = _importance_stars(n.get("importance", 0.5))
            lines.append(f"- **{n.get('name', '')}** {stars}")
        lines.append("")

    # Detailed concept sections
    lines.append("---")
    lines.append("")
    lines.append("## 详细笔记")
    lines.append("")

    for node in sorted_nodes:
        cid = node.get("id", "")
        name = node.get("name", cid)
        lines.append(f"### {name}")
        lines.append("")

        # Metadata
        meta_parts = []
        if node.get("type"):
            meta_parts.append(f"类型: {node['type']}")
        if node.get("difficulty"):
            meta_parts.append(f"难度: {node['difficulty']}")
        meta_parts.append(f"重要度: {node.get('importance', 0.5):.1f}/1.0")
        if meta_parts:
            lines.append(f"> {' | '.join(meta_parts)}")
            lines.append("")

        # Definition
        definition = node.get("definition", "")
        if definition and definition != "暂无定义":
            lines.append(f"**定义:** {definition}")
            lines.append("")

        # Explanation
        explanation = node.get("explanation", "")
        if explanation:
            lines.append(explanation)
            lines.append("")

        # Key points
        key_points = _flatten(node.get("key_points", []))
        if key_points:
            lines.append("**关键要点:**")
            lines.append("")
            for kp in key_points:
                lines.append(f"- {kp}")
            lines.append("")

        # Examples
        examples = _flatten(node.get("examples", []))
        if examples:
            lines.append("**示例:**")
            lines.append("")
            for ex in examples:
                lines.append(f"- {ex}")
            lines.append("")

        # Common mistakes
        mistakes = _flatten(node.get("common_mistakes", []))
        if mistakes:
            lines.append("**常见误区:**")
            lines.append("")
            for m in mistakes:
                lines.append(f"- {m}")
            lines.append("")

        # Learning tips
        tips = node.get("learning_tips", "")
        if tips:
            lines.append(f"**学习建议:** {tips}")
            lines.append("")

        # Prerequisites & next steps
        my_edges = edge_index.get(cid, [])
        prereqs = [e for e in my_edges if e["type"] == "prerequisite" and e["to"] == cid]
        extends = [e for e in my_edges if e["type"] == "prerequisite" and e["from"] == cid]

        if prereqs:
            names = [_edge_label(nodes, e, "from") for e in prereqs]
            lines.append(f"**前置知识:** {', '.join(names)}")
            lines.append("")

        if extends:
            names = [_edge_label(nodes, e, "to") for e in extends]
            lines.append(f"**进阶方向:** {', '.join(names)}")
            lines.append("")

        # Related concepts
        related = [e for e in my_edges if e["type"] == "related"]
        if related:
            names = [_edge_label(nodes, e, "other", ref_id=cid) for e in related]
            lines.append(f"**相关概念:** {', '.join(names)}")
            lines.append("")

        # Resources
        resources = res_map.get(cid, [])
        if resources:
            lines.append("**推荐资源:**")
            lines.append("")
            for r in resources[:5]:
                title = r.get("title", "")
                url = r.get("url", "")
                score = r.get("quality_score", 0)
                lines.append(f"- [{title}]({url}) (质量: {score:.1f}/10)")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ── Anki Export ─────────────────────────────────────────────


def export_anki(
    knowledge_graph: dict,
    knowledge_resources: dict[str, list[dict]] | None = None,
    deck_name: str = "OpenLearning",
) -> str:
    """Export knowledge graph as Anki-compatible text cards.

    Generates three card types:
    1. Definition cards (cloze-style): "什么是 X? → definition"
    2. Key-point cards (basic Q&A): question → answer
    3. Relationship cards: "X 的前置知识是? → Y"

    Args:
        knowledge_graph: {nodes: [...], edges: [...]}
        knowledge_resources: optional resource mapping
        deck_name: Anki deck name

    Returns:
        Anki text export string (tab-separated, importable as "Text File").
    """
    nodes = knowledge_graph.get("nodes", [])
    edges = knowledge_graph.get("edges", [])
    res_map = knowledge_resources or {}

    # Build edge index
    edge_index: dict[str, list[dict]] = {}
    for e in edges:
        for cid in (e.get("from"), e.get("to")):
            edge_index.setdefault(cid, []).append(e)

    cards: list[dict] = []

    for node in nodes:
        cid = node.get("id", "")
        name = node.get("name", cid)
        definition = node.get("definition", "")
        explanation = node.get("explanation", "")
        key_points = _flatten(node.get("key_points", []))
        difficulty = node.get("difficulty", "")
        common_mistakes = _flatten(node.get("common_mistakes", []))

        # Tag prefix for difficulty
        diff_tag = difficulty or "general"

        # Card Type 1: Definition
        if definition and definition != "暂无定义":
            cards.append({
                "front": f"什么是 {name}？",
                "back": definition,
                "tags": f"{diff_tag} definition",
            })

        # Card Type 2: Explanation summary (first paragraph as Q&A)
        if explanation:
            first_para = explanation.split("\n")[0].strip()
            if len(first_para) > 20:
                cards.append({
                    "front": f"请简要解释 {name} 的核心概念",
                    "back": first_para,
                    "tags": f"{diff_tag} explanation",
                })

        # Card Type 3: Key points (one card per point)
        for i, kp in enumerate(key_points):
            if len(kp) > 10:
                cards.append({
                    "front": f"关于 {name}，以下要点是什么？\n（提示：第 {i+1} 个要点）",
                    "back": kp,
                    "tags": f"{diff_tag} key-point",
                })

        # Card Type 4: Common mistakes
        for i, mistake in enumerate(common_mistakes):
            if len(mistake) > 10:
                cards.append({
                    "front": f"学习 {name} 时的常见误区 #{i+1} 是什么？",
                    "back": mistake,
                    "tags": f"{diff_tag} mistake",
                })

        # Card Type 5: Prerequisites
        my_edges = edge_index.get(cid, [])
        prereqs = [e for e in my_edges if e["type"] == "prerequisite" and e["to"] == cid]
        if prereqs:
            prereq_names = [_find_node_name(nodes, e["from"]) for e in prereqs]
            cards.append({
                "front": f"学习 {name} 之前，需要掌握哪些前置知识？",
                "back": "、".join(prereq_names),
                "tags": f"{diff_tag} prerequisite",
            })

        # Card Type 6: Next steps
        extends = [e for e in my_edges if e["type"] == "prerequisite" and e["from"] == cid]
        if extends:
            next_names = [_find_node_name(nodes, e["to"]) for e in extends]
            cards.append({
                "front": f"掌握 {name} 之后，下一步应该学什么？",
                "back": "、".join(next_names),
                "tags": f"{diff_tag} next-step",
            })

    # Format as Anki text export
    # Tab-separated: front\tback\ttags
    lines = [f"#deck:{deck_name}"]
    for card in cards:
        front = _escape_anki(card["front"])
        back = _escape_anki(card["back"])
        tags = card["tags"]
        lines.append(f"{front}\t{back}\t{tags}")

    return "\n".join(lines)


# ── CSV Export (for spreadsheet analysis) ───────────────────


def export_csv(knowledge_graph: dict) -> str:
    """Export concepts as CSV for spreadsheet analysis."""
    nodes = knowledge_graph.get("nodes", [])
    edges = knowledge_graph.get("edges", [])

    edge_index: dict[str, list[dict]] = {}
    for e in edges:
        for cid in (e.get("from"), e.get("to")):
            edge_index.setdefault(cid, []).append(e)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "type", "difficulty", "importance",
        "definition", "prerequisites", "next_steps",
        "key_points_count", "has_examples",
    ])

    for node in nodes:
        cid = node.get("id", "")
        my_edges = edge_index.get(cid, [])
        prereqs = [_find_node_name(nodes, e["from"])
                   for e in my_edges if e["type"] == "prerequisite" and e["to"] == cid]
        extends = [_find_node_name(nodes, e["to"])
                   for e in my_edges if e["type"] == "prerequisite" and e["from"] == cid]

        writer.writerow([
            cid,
            node.get("name", ""),
            node.get("type", ""),
            node.get("difficulty", ""),
            f"{node.get('importance', 0.5):.2f}",
            (node.get("definition", "") or "")[:100],
            "; ".join(prereqs),
            "; ".join(extends),
            len(_flatten(node.get("key_points", []))),
            "是" if node.get("examples") else "否",
        ])

    return output.getvalue()


# ── Helpers ─────────────────────────────────────────────────


def _flatten(items: list) -> list[str]:
    """Flatten nested list into flat list of strings."""
    result = []
    for item in items:
        if isinstance(item, list):
            result.extend(str(i) for i in item if i)
        elif isinstance(item, str) and item:
            result.append(item)
    return result


def _find_node(nodes: list[dict], cid: str) -> dict | None:
    for n in nodes:
        if n.get("id") == cid:
            return n
    return None


def _find_node_name(nodes: list[dict], cid: str) -> str:
    n = _find_node(nodes, cid)
    return n.get("name", cid) if n else cid


def _edge_label(nodes: list[dict], edge: dict, side: str, ref_id: str = "") -> str:
    if side == "other":
        other_id = edge["to"] if edge.get("from") == ref_id else edge["from"]
    else:
        other_id = edge.get(side, "")
    name = _find_node_name(nodes, other_id)
    reason = edge.get("reason", "")
    if reason:
        return f"{name}（{reason}）"
    return name


def _importance_stars(importance: float) -> str:
    full = int(importance * 5)
    return "★" * full + "☆" * (5 - full)


def _md_anchor(text: str) -> str:
    """Convert text to GitHub-style markdown anchor."""
    anchor = text.lower().strip()
    anchor = re.sub(r"[^\w\s一-鿿-]", "", anchor)
    anchor = re.sub(r"[\s]+", "-", anchor)
    return anchor


def _escape_anki(text: str) -> str:
    """Escape text for Anki import (preserve newlines as <br>)."""
    return text.replace("\n", "<br>")
