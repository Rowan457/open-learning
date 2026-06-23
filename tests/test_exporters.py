"""Tests for Exporters — Markdown notes & Anki cards."""

import pytest


# ── Fixtures ────────────────────────────────────────────────


def _sample_graph():
    """Minimal knowledge graph for testing."""
    return {
        "nodes": [
            {
                "id": "ownership",
                "name": "所有权",
                "type": "concept",
                "difficulty": "beginner",
                "importance": 0.9,
                "definition": "Rust 的所有权系统是内存安全的核心机制",
                "explanation": "每个值都有一个所有者，当所有者离开作用域时，值被丢弃。",
                "key_points": ["每个值有唯一所有者", "作用域结束时自动释放", "赋值会转移所有权"],
                "examples": ["let s1 = String::from(\"hello\"); let s2 = s1; // s1 不再有效"],
                "common_mistakes": ["使用已移动的变量"],
                "learning_tips": "多画内存图来理解所有权转移",
            },
            {
                "id": "borrowing",
                "name": "借用",
                "type": "concept",
                "difficulty": "intermediate",
                "importance": 0.8,
                "definition": "通过引用借用值而不获取所有权",
                "explanation": "借用允许你引用某个值而不获取其所有权。",
                "key_points": ["不可变借用 &T", "可变借用 &mut T", "同一时间只能有一个可变借用"],
                "examples": ["fn calculate_length(s: &String) -> usize { s.len() }"],
                "common_mistakes": ["同时持有可变和不可引用"],
            },
            {
                "id": "lifetimes",
                "name": "生命周期",
                "type": "concept",
                "difficulty": "advanced",
                "importance": 0.7,
                "definition": "确保引用在使用期间始终有效",
            },
        ],
        "edges": [
            {"from": "ownership", "to": "borrowing", "type": "prerequisite", "weight": 0.9,
             "reason": "必须先理解所有权才能理解借用"},
            {"from": "borrowing", "to": "lifetimes", "type": "prerequisite", "weight": 0.8},
            {"from": "ownership", "to": "lifetimes", "type": "related", "weight": 0.5},
        ],
    }


def _sample_learning_path():
    return {
        "phases": [
            {"name": "基础", "difficulty": "beginner", "concept_ids": ["ownership"]},
            {"name": "进阶", "difficulty": "intermediate", "concept_ids": ["borrowing", "lifetimes"]},
        ]
    }


# ── Markdown Export ─────────────────────────────────────────


class TestExportMarkdown:
    def test_basic_structure(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph(), project_title="Rust 学习笔记")
        assert "# Rust 学习笔记" in md
        assert "## 目录" in md
        assert "## 详细笔记" in md

    def test_contains_all_concepts(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "所有权" in md
        assert "借用" in md
        assert "生命周期" in md

    def test_contains_definitions(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "Rust 的所有权系统是内存安全的核心机制" in md
        assert "通过引用借用值而不获取所有权" in md

    def test_contains_key_points(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "每个值有唯一所有者" in md
        assert "不可变借用 &T" in md

    def test_contains_examples(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "let s1 = String::from" in md

    def test_contains_mistakes(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "使用已移动的变量" in md
        assert "同时持有可变和不可变引用" in md

    def test_contains_prerequisites(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "前置知识" in md
        # borrowing's prerequisite is ownership
        assert "所有权" in md

    def test_contains_edge_reasons(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "必须先理解所有权才能理解借用" in md

    def test_learning_path_section(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph(), learning_path=_sample_learning_path())
        assert "## 学习路径" in md
        assert "基础" in md

    def test_difficulty_grouping(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "入门" in md or "beginner" in md
        assert "进阶" in md or "advanced" in md

    def test_resource_links(self):
        from openlearning.exporters import export_markdown

        res_map = {
            "ownership": [
                {"title": "Rust Book Ch4", "url": "https://doc.rust-lang.org/book/ch04-00.html", "quality_score": 9.0},
            ]
        }
        md = export_markdown(_sample_graph(), knowledge_resources=res_map)
        assert "Rust Book Ch4" in md
        assert "https://doc.rust-lang.org" in md

    def test_metadata_line(self):
        from openlearning.exporters import export_markdown

        md = export_markdown(_sample_graph())
        assert "3 个概念" in md
        assert "3 条关系" in md


# ── Anki Export ─────────────────────────────────────────────


class TestExportAnki:
    def test_deck_header(self):
        from openlearning.exporters import export_anki

        txt = export_anki(_sample_graph(), deck_name="Rust 基础")
        assert "#deck:Rust 基础" in txt

    def test_definition_cards(self):
        from openlearning.exporters import export_anki

        txt = export_anki(_sample_graph())
        assert "什么是 所有权" in txt
        assert "所有权系统是内存安全" in txt

    def test_key_point_cards(self):
        from openlearning.exporters import export_anki

        txt = export_anki(_sample_graph())
        assert "每个值有唯一所有者" in txt

    def test_mistake_cards(self):
        from openlearning.exporters import export_anki

        txt = export_anki(_sample_graph())
        assert "常见误区" in txt

    def test_prerequisite_cards(self):
        from openlearning.exporters import export_anki

        txt = export_anki(_sample_graph())
        assert "前置知识" in txt
        assert "所有权" in txt

    def test_tab_separated(self):
        from openlearning.exporters import export_anki

        txt = export_anki(_sample_graph())
        lines = [l for l in txt.split("\n") if l and not l.startswith("#")]
        for line in lines:
            parts = line.split("\t")
            assert len(parts) == 3, f"Expected 3 tab-separated fields, got {len(parts)}: {line}"

    def test_tags_contain_difficulty(self):
        from openlearning.exporters import export_anki

        txt = export_anki(_sample_graph())
        assert "beginner" in txt
        assert "intermediate" in txt
        assert "advanced" in txt

    def test_no_empty_definitions(self):
        """Nodes without definitions should not generate definition cards."""
        from openlearning.exporters import export_anki

        graph = {
            "nodes": [{"id": "x", "name": "NoDef", "type": "concept", "difficulty": "beginner", "importance": 0.5}],
            "edges": [],
        }
        txt = export_anki(graph)
        assert "什么是 NoDef" not in txt

    def test_next_step_cards(self):
        from openlearning.exporters import export_anki

        txt = export_anki(_sample_graph())
        assert "下一步应该学什么" in txt


# ── CSV Export ──────────────────────────────────────────────


class TestExportCsv:
    def test_header_row(self):
        from openlearning.exporters import export_csv

        csv_str = export_csv(_sample_graph())
        first_line = csv_str.split("\n")[0]
        assert "id" in first_line
        assert "name" in first_line
        assert "difficulty" in first_line

    def test_data_rows(self):
        from openlearning.exporters import export_csv

        csv_str = export_csv(_sample_graph())
        lines = csv_str.strip().split("\n")
        assert len(lines) == 4  # header + 3 nodes

    def test_prerequisites_column(self):
        from openlearning.exporters import export_csv

        csv_str = export_csv(_sample_graph())
        assert "所有权" in csv_str  # borrowing's prerequisite


# ── Helpers ─────────────────────────────────────────────────


class TestHelpers:
    def test_flatten(self):
        from openlearning.exporters import _flatten

        assert _flatten(["a", "b"]) == ["a", "b"]
        assert _flatten([["a", "b"], "c"]) == ["a", "b", "c"]
        assert _flatten([]) == []

    def test_importance_stars(self):
        from openlearning.exporters import _importance_stars

        assert _importance_stars(1.0) == "★★★★★"
        assert _importance_stars(0.0) == "☆☆☆☆☆"
        assert _importance_stars(0.5) == "★★☆☆☆"

    def test_md_anchor(self):
        from openlearning.exporters import _md_anchor

        assert _md_anchor("Hello World") == "hello-world"
        assert _md_anchor("所有权") == "所有权"

    def test_escape_anki(self):
        from openlearning.exporters import _escape_anki

        assert _escape_anki("line1\nline2") == "line1<br>line2"
