"""Render Skill — static site generation.

Tools: build_learning_system, preview, deploy
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from openlearning.config import get_config


# ── Input Schemas ────────────────────────────────────────────

class BuildInput(BaseModel):
    knowledge_graph: dict = Field(description="知识图谱数据")
    learning_path: dict = Field(default_factory=dict, description="学习路径")
    knowledge_resources: dict = Field(default_factory=dict, description="概念→资源映射")
    output_dir: str = Field(default="./output/", description="输出目录")


class PreviewInput(BaseModel):
    port: int = Field(default=8080, description="预览服务器端口")


class DeployInput(BaseModel):
    target: str = Field(default="local", description="部署目标: local / github-pages")
    output_dir: str = Field(default="./output/", description="站点目录")


# ── Build Learning System ────────────────────────────────────

@tool("build_learning_system", args_schema=BuildInput)
async def build_learning_system(
    knowledge_graph: dict,
    learning_path: dict | None = None,
    knowledge_resources: dict | None = None,
    output_dir: str = "./output/",
) -> dict[str, Any]:
    """生成知识图谱驱动的学习系统站点。

    生成结构: index.html, graph.html, learning-path.html, bookmarks.html, knowledge/*.html, data/*.json
    返回 {site_path, pages_generated}。
    """
    config = get_config()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    path_data = learning_path or {}
    res_map = knowledge_resources or {}
    nodes = knowledge_graph.get("nodes", [])
    edges = knowledge_graph.get("edges", [])

    pages_generated = 0

    # 1. Generate index.html
    html = _builtin_index(knowledge_graph, path_data, config.site)
    (out / "index.html").write_text(html, encoding="utf-8")
    pages_generated += 1

    # 2. Generate graph.html
    graph_html = _builtin_graph(nodes, edges, config.site)
    (out / "graph.html").write_text(graph_html, encoding="utf-8")
    pages_generated += 1

    # 3. Generate learning-path.html
    path_html = _builtin_learning_path(path_data, nodes, edges, config.site)
    (out / "learning-path.html").write_text(path_html, encoding="utf-8")
    pages_generated += 1

    # 4. Generate bookmarks.html
    bookmarks_html = _builtin_bookmarks(nodes, config.site)
    (out / "bookmarks.html").write_text(bookmarks_html, encoding="utf-8")
    pages_generated += 1

    # 5. Generate per-concept pages
    knowledge_dir = out / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)

    # Build ordered node list for prev/next navigation
    sorted_nodes = sorted(nodes, key=lambda n: n.get("importance", 0.5), reverse=True)

    for i, node in enumerate(sorted_nodes):
        concept_id = node.get("id", "")
        safe_id = _safe_filename(concept_id)
        prev_node = sorted_nodes[i - 1] if i > 0 else None
        next_node = sorted_nodes[i + 1] if i < len(sorted_nodes) - 1 else None
        concept_html = _builtin_concept_page(node, edges, res_map, config.site, prev_node, next_node)
        (knowledge_dir / f"{safe_id}.html").write_text(concept_html, encoding="utf-8")
        pages_generated += 1

    # 6. Generate data JSON files
    data_dir = out / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "knowledge-graph.json").write_text(
        json.dumps(knowledge_graph, ensure_ascii=False, indent=2)
    )
    (data_dir / "learning-path.json").write_text(
        json.dumps(path_data, ensure_ascii=False, indent=2)
    )

    return {
        "site_path": str(out.resolve()),
        "pages_generated": pages_generated,
    }


# ── Preview ──────────────────────────────────────────────────

@tool("preview", args_schema=PreviewInput)
async def preview(port: int = 8080) -> dict[str, Any]:
    """启动本地预览服务器。"""
    config = get_config()
    output_dir = Path(config.output_dir)

    if not output_dir.exists():
        return {"error": "No output directory found. Run build first."}

    import functools
    import http.server
    import threading

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(output_dir),
    )
    server = http.server.HTTPServer(("", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return {"url": f"http://localhost:{port}", "port": port, "status": "running"}


# ── Deploy ───────────────────────────────────────────────────

@tool("deploy", args_schema=DeployInput)
async def deploy(target: str = "local", output_dir: str = "./output/") -> dict[str, Any]:
    """部署生成的站点。"""
    if target == "local":
        return {"url": str(Path(output_dir).resolve()), "target": "local", "status": "deployed"}
    return {"error": f"Unsupported deploy target: {target}"}


# ── Helpers ──────────────────────────────────────────────────

def _safe_filename(concept_id: str) -> str:
    """Sanitize concept ID for use as a filename."""
    return (concept_id
            .replace("/", "_").replace("\\", "_").replace(":", "_")
            .replace("*", "_").replace("?", "_").replace('"', "_")
            .replace("<", "_").replace(">", "_").replace("|", "_"))


def _esc(s) -> str:
    """Escape HTML, handle non-string types."""
    if isinstance(s, list):
        s = " ".join(str(item) for item in s)
    elif not isinstance(s, str):
        s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _type_color(node_type: str) -> str:
    """Return Tailwind color class for node type."""
    colors = {
        "concept": "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
        "technology": "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
        "principle": "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
        "practice": "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
        "project": "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
        "application": "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
    }
    return colors.get(node_type, colors["concept"])


def _difficulty_color(diff: str) -> str:
    """Return Tailwind color class for difficulty."""
    colors = {
        "beginner": "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
        "intermediate": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
        "advanced": "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    }
    return colors.get(diff, colors["intermediate"])


def _importance_stars(importance: float) -> str:
    """Convert importance 0-1 to star display."""
    stars = round(importance * 5)
    return "★" * stars + "☆" * (5 - stars)


# ── Built-in Templates ──────────────────────────────────────

def _builtin_index(graph: dict, path: dict, site_config) -> str:
    """Generate index.html with all nodes, type filter, lazy loading."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Sort by importance descending
    nodes_sorted = sorted(nodes, key=lambda n: n.get("importance", 0.5), reverse=True)

    # Prepare nodes data for search (all nodes)
    nodes_json = json.dumps([{
        "id": n.get("id", ""), "name": n.get("name", ""),
        "type": n.get("type", "concept"), "difficulty": n.get("difficulty", "intermediate"),
        "importance": n.get("importance", 0.5),
    } for n in nodes_sorted])

    # Collect unique types and difficulties
    types = sorted(set(n.get("type", "concept") for n in nodes))
    difficulties = sorted(set(n.get("difficulty", "intermediate") for n in nodes))

    # Type filter buttons
    type_buttons = '<button onclick="filterBy(\'type\',\'all\',this)" class="type-btn px-3 py-1 rounded-full text-sm bg-blue-600 text-white">全部类型</button>'
    for t in types:
        type_buttons += f'<button onclick="filterBy(\'type\',\'{t}\',this)" class="type-btn px-3 py-1 rounded-full text-sm bg-gray-200 dark:bg-gray-700 dark:text-gray-200">{t}</button>'

    # Difficulty filter buttons
    diff_buttons = '<button onclick="filterBy(\'difficulty\',\'all\',this)" class="diff-btn px-3 py-1 rounded-full text-sm bg-blue-600 text-white">全部难度</button>'
    for d in difficulties:
        diff_buttons += f'<button onclick="filterBy(\'difficulty\',\'{d}\',this)" class="diff-btn px-3 py-1 rounded-full text-sm bg-gray-200 dark:bg-gray-700 dark:text-gray-200">{d}</button>'

    # Type distribution bar
    type_counts = {}
    for n in nodes:
        t = n.get("type", "concept")
        type_counts[t] = type_counts.get(t, 0) + 1
    total = len(nodes) or 1
    type_bar_segments = []
    bar_colors = {"concept": "#3B82F6", "technology": "#F59E0B", "principle": "#10B981",
                  "practice": "#8B5CF6", "project": "#EC4899", "application": "#06B6D4"}
    for t, cnt in type_counts.items():
        pct = cnt / total * 100
        color = bar_colors.get(t, "#6B7280")
        type_bar_segments.append(f'<div style="width:{pct:.1f}%;background:{color}" title="{t}: {cnt}" class="h-2"></div>')
    type_bar = f'<div class="flex rounded-full overflow-hidden h-2 mb-6">{"".join(type_bar_segments)}</div>'

    # Generate ALL node cards (not just 20)
    cards_html = ""
    for n in nodes_sorted:
        nid = _safe_filename(n.get("id", ""))
        name = _esc(n.get("name", ""))
        ntype = n.get("type", "concept")
        diff = n.get("difficulty", "intermediate")
        importance = n.get("importance", 0.5)
        stars = _importance_stars(importance)
        cards_html += f'''<a href="knowledge/{nid}.html" class="node-card bg-white dark:bg-gray-800 rounded-lg shadow p-4 hover:shadow-lg transition-shadow" data-id="{_esc(n.get('id', ''))}" data-type="{ntype}" data-difficulty="{diff}" data-importance="{importance}">
            <h3 class="font-semibold dark:text-white text-sm">{name}</h3>
            <div class="flex items-center gap-2 mt-2 flex-wrap">
                <span class="px-2 py-0.5 rounded text-xs {_type_color(ntype)}">{ntype}</span>
                <span class="px-2 py-0.5 rounded text-xs {_difficulty_color(diff)}">{diff}</span>
                <span class="text-xs text-yellow-500" title="重要度 {importance:.1f}">{stars}</span>
            </div>
        </a>'''

    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenLearning - 知识图谱学习系统</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/fuse.js@7/dist/fuse.min.js"></script>
    <script>tailwind.config = {{ darkMode: 'class' }}</script>
</head>
<body class="bg-gray-50 dark:bg-gray-900 min-h-screen transition-colors">
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div>
                <h1 class="text-2xl font-bold text-gray-900 dark:text-white">OpenLearning</h1>
                <p class="text-gray-600 dark:text-gray-400 mt-1">知识图谱驱动的智能学习系统</p>
            </div>
            <div class="flex items-center gap-2">
                <a href="bookmarks.html" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl hover:bg-gray-200 dark:hover:bg-gray-600" title="收藏夹">⭐</a>
                <button onclick="document.documentElement.classList.toggle('dark')" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl">🌓</button>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-8">
        <!-- 搜索框 -->
        <div class="mb-6">
            <input id="search-input" type="text" placeholder="搜索知识点..." class="w-full max-w-md px-4 py-2 rounded-lg border dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none">
            <span id="result-count" class="ml-2 text-sm text-gray-500 dark:text-gray-400">{len(nodes)} 个知识点</span>
        </div>

        <!-- 统计卡片 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold text-gray-700 dark:text-gray-300">知识点</h3>
                <p class="text-3xl font-bold text-blue-600">{len(nodes)}</p>
            </div>
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold text-gray-700 dark:text-gray-300">关联关系</h3>
                <p class="text-3xl font-bold text-green-600">{len(edges)}</p>
            </div>
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold text-gray-700 dark:text-gray-300">学习路径</h3>
                <p class="text-3xl font-bold text-purple-600">{len(path.get('steps', []))} 步</p>
            </div>
        </div>

        <!-- 类型分布条 -->
        <div class="mb-6">
            <p class="text-sm text-gray-500 dark:text-gray-400 mb-1">类型分布</p>
            {type_bar}
        </div>

        <!-- 快捷入口 -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <a href="graph.html" class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold mb-2 dark:text-white">🗺️ 知识图谱</h2>
                <p class="text-gray-600 dark:text-gray-400">交互式知识图谱，全局视角理解知识结构</p>
            </a>
            <a href="learning-path.html" class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold mb-2 dark:text-white">📚 学习路径</h2>
                <p class="text-gray-600 dark:text-gray-400">个性化学习路径，循序渐进掌握知识</p>
            </a>
            <a href="bookmarks.html" class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold mb-2 dark:text-white">⭐ 我的收藏</h2>
                <p class="text-gray-600 dark:text-gray-400">查看和管理收藏的知识点</p>
            </a>
        </div>

        <!-- 筛选器 -->
        <div class="mb-4">
            <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">类型筛选</p>
            <div class="flex flex-wrap gap-2 mb-3">{type_buttons}</div>
            <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">难度筛选</p>
            <div class="flex flex-wrap gap-2">{diff_buttons}</div>
        </div>

        <!-- 知识点列表 -->
        <section>
            <div id="nodes-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {cards_html}
            </div>
            <p id="no-results" class="hidden text-gray-500 dark:text-gray-400 text-center py-8">未找到匹配的知识点</p>
        </section>
    </main>

    <script>
        const nodesData = {nodes_json};
        const fuse = new Fuse(nodesData, {{ keys: ['name', 'type', 'difficulty'], threshold: 0.4 }});

        // Current filter state
        let currentType = 'all';
        let currentDifficulty = 'all';
        let currentSearch = '';

        function applyFilters() {{
            const cards = document.querySelectorAll('.node-card');
            const noResults = document.getElementById('no-results');
            const countEl = document.getElementById('result-count');
            let shown = 0;

            // Get search results if searching
            let searchIds = null;
            if (currentSearch) {{
                searchIds = new Set(fuse.search(currentSearch).map(r => r.item.id));
            }}

            cards.forEach(card => {{
                const cardType = card.dataset.type;
                const cardDiff = card.dataset.difficulty;
                const cardId = card.dataset.id;

                let visible = true;
                if (currentType !== 'all' && cardType !== currentType) visible = false;
                if (currentDifficulty !== 'all' && cardDiff !== currentDifficulty) visible = false;
                if (searchIds && !searchIds.has(cardId)) visible = false;

                card.style.display = visible ? '' : 'none';
                if (visible) shown++;
            }});

            noResults.classList.toggle('hidden', shown > 0);
            countEl.textContent = shown + ' 个知识点';
        }}

        // Search
        document.getElementById('search-input').addEventListener('input', function(e) {{
            currentSearch = e.target.value.trim();
            applyFilters();
        }});

        // Filter by type or difficulty
        function filterBy(dim, value, btn) {{
            if (dim === 'type') {{
                currentType = value;
                document.querySelectorAll('.type-btn').forEach(b => {{
                    b.classList.remove('bg-blue-600', 'text-white');
                    b.classList.add('bg-gray-200', 'dark:bg-gray-700');
                }});
            }} else {{
                currentDifficulty = value;
                document.querySelectorAll('.diff-btn').forEach(b => {{
                    b.classList.remove('bg-blue-600', 'text-white');
                    b.classList.add('bg-gray-200', 'dark:bg-gray-700');
                }});
            }}
            btn.classList.remove('bg-gray-200', 'dark:bg-gray-700');
            btn.classList.add('bg-blue-600', 'text-white');
            applyFilters();
        }}
    </script>
</body>
</html>"""


def _builtin_graph(nodes: list, edges: list, site_config) -> str:
    """Generate graph.html with search, tooltip, legend, layout switcher."""
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知识图谱 - OpenLearning</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/cytoscape@3.28.0/dist/cytoscape.min.js"></script>
    <script>tailwind.config = {{ darkMode: 'class' }}</script>
    <style>
        #tooltip {{ position: absolute; display: none; z-index: 1000; max-width: 300px; pointer-events: none; }}
    </style>
</head>
<body class="bg-gray-50 dark:bg-gray-900 transition-colors">
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <a href="index.html" class="text-blue-600 dark:text-blue-400 hover:underline">← 返回</a>
                <h1 class="text-xl font-bold dark:text-white">知识图谱</h1>
            </div>
            <div class="flex items-center gap-2">
                <input id="graph-search" type="text" placeholder="搜索节点..." class="px-3 py-1 rounded-lg border dark:border-gray-600 dark:bg-gray-800 dark:text-white text-sm w-48">
                <select id="layout-select" onchange="changeLayout(this.value)" class="px-2 py-1 rounded-lg border dark:border-gray-600 dark:bg-gray-800 dark:text-white text-sm">
                    <option value="breadthfirst">层次布局</option>
                    <option value="cose">力导向</option>
                    <option value="circle">环形</option>
                    <option value="grid">网格</option>
                </select>
                <button onclick="document.documentElement.classList.toggle('dark'); updateTheme()" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl">🌓</button>
            </div>
        </div>
    </header>
    <div id="cy" style="width: 100%; height: calc(100vh - 130px);"></div>

    <!-- Tooltip -->
    <div id="tooltip" class="bg-white dark:bg-gray-800 rounded-lg shadow-lg border dark:border-gray-700 p-3">
        <div id="tooltip-title" class="font-semibold dark:text-white text-sm"></div>
        <div id="tooltip-meta" class="text-xs text-gray-500 dark:text-gray-400 mt-1"></div>
        <div id="tooltip-def" class="text-xs text-gray-600 dark:text-gray-300 mt-1"></div>
    </div>

    <!-- Legend -->
    <div class="fixed bottom-4 right-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg border dark:border-gray-700 p-3 text-xs z-50">
        <p class="font-semibold dark:text-white mb-2">图例</p>
        <div class="space-y-1">
            <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-blue-500"></span><span class="dark:text-gray-300">概念</span></div>
            <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-amber-500"></span><span class="dark:text-gray-300">技术</span></div>
            <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-green-500"></span><span class="dark:text-gray-300">原理</span></div>
            <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-purple-500"></span><span class="dark:text-gray-300">实践</span></div>
            <hr class="dark:border-gray-600 my-1">
            <div class="flex items-center gap-2"><span class="w-6 h-0.5 bg-gray-400"></span><span class="dark:text-gray-300">相关</span></div>
            <div class="flex items-center gap-2"><span class="w-6 h-0.5 bg-red-400 border-dashed" style="border-top:2px dashed #f87171;height:0"></span><span class="dark:text-gray-300">前置</span></div>
        </div>
    </div>

    <script>
        const nodes = {nodes_json};
        const edges = {edges_json};

        const typeColors = {{concept:'#3B82F6',technology:'#F59E0B',principle:'#10B981',practice:'#8B5CF6',project:'#EC4899',application:'#06B6D4'}};

        const cy = cytoscape({{
            container: document.getElementById('cy'),
            elements: [
                ...nodes.map(n => ({{ data: {{ id: n.id, label: n.name, type: n.type, difficulty: n.difficulty, definition: (n.definition||'').substring(0,80) }} }})),
                ...edges.map(e => ({{ data: {{ source: e.from, target: e.to, type: e.type, weight: e.weight, reason: e.reason || '' }} }})),
            ],
            style: [
                {{ selector: 'node', style: {{ label: 'data(label)', 'background-color': function(el) {{ return typeColors[el.data('type')] || '#3B82F6'; }}, color: '#fff', 'text-valign': 'center', 'font-size': '11px', width: 36, height: 36, 'text-wrap': 'ellipsis', 'text-max-width': '80px' }} }},
                {{ selector: 'node.highlighted', style: {{ 'border-width': 3, 'border-color': '#EF4444', width: 48, height: 48 }} }},
                {{ selector: 'node.dimmed', style: {{ 'opacity': 0.2 }} }},
                {{ selector: 'edge', style: {{ width: 1.5, 'line-color': '#94A3B8', 'target-arrow-color': '#94A3B8', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier' }} }},
                {{ selector: 'edge[type="prerequisite"]', style: {{ 'line-color': '#EF4444', 'target-arrow-color': '#EF4444', 'line-style': 'dashed', width: 2 }} }},
                {{ selector: 'edge.dimmed', style: {{ 'opacity': 0.1 }} }},
            ],
            layout: {{ name: 'breadthfirst', directed: true, spacingFactor: 1.5 }},
        }});

        // Click to navigate
        cy.on('tap', 'node', function(evt) {{
            const id = evt.target.id().replace(/[/\\\\:*?"<>|]/g, '_');
            window.location.href = 'knowledge/' + id + '.html';
        }});

        // Hover tooltip
        const tooltip = document.getElementById('tooltip');
        cy.on('mouseover', 'node', function(evt) {{
            const d = evt.target.data();
            document.getElementById('tooltip-title').textContent = d.label;
            document.getElementById('tooltip-meta').textContent = d.type + ' · ' + d.difficulty;
            document.getElementById('tooltip-def').textContent = d.definition || '';
            tooltip.style.display = 'block';
        }});
        cy.on('mousemove', function(evt) {{
            tooltip.style.left = (evt.originalEvent.clientX + 15) + 'px';
            tooltip.style.top = (evt.originalEvent.clientY + 15) + 'px';
        }});
        cy.on('mouseout', 'node', function() {{
            tooltip.style.display = 'none';
        }});

        // Search
        document.getElementById('graph-search').addEventListener('input', function(e) {{
            const q = e.target.value.trim().toLowerCase();
            if (!q) {{
                cy.elements().removeClass('highlighted dimmed');
                return;
            }}
            cy.nodes().forEach(n => {{
                const match = n.data('label').toLowerCase().includes(q);
                n.toggleClass('highlighted', match);
                n.toggleClass('dimmed', !match);
            }});
            cy.edges().addClass('dimmed');
            // Un-dim edges connected to highlighted nodes
            cy.edges().forEach(e => {{
                if (e.source().hasClass('highlighted') || e.target().hasClass('highlighted')) {{
                    e.removeClass('dimmed');
                }}
            }});
        }});

        // Layout switcher
        function changeLayout(name) {{
            cy.layout({{ name: name, directed: name === 'breadthfirst', spacingFactor: 1.5, animate: true }}).run();
        }}

        // Dark mode theme update
        function updateTheme() {{
            const isDark = document.documentElement.classList.contains('dark');
            cy.nodes().forEach(n => {{
                n.style('color', isDark ? '#1F2937' : '#fff');
            }});
        }}
    </script>
</body>
</html>"""


def _builtin_learning_path(path: dict, nodes: list, edges: list, site_config) -> str:
    """Generate learning-path.html with prerequisite graph and progress tracking."""
    steps = path.get("steps", [])
    node_map = {n["id"]: n for n in nodes}

    # Build prerequisite edge map for Mermaid
    prereq_edges = [e for e in edges if e.get("type") == "prerequisite"]

    # Group steps by difficulty
    groups = {"入门": [], "基础": [], "进阶": [], "高级": []}
    for step in steps:
        cid = step.get("concept", "")
        node = node_map.get(cid, {})
        diff = node.get("difficulty", "intermediate")
        if diff == "beginner":
            groups["入门"].append(step)
        elif diff == "advanced":
            groups["高级"].append(step)
        else:
            # Split intermediate into 基础 and 进阶 by importance
            imp = node.get("importance", 0.5)
            if imp >= 0.5:
                groups["进阶"].append(step)
            else:
                groups["基础"].append(step)

    # Build Mermaid chart using prerequisite edges (limited to 50 for readability)
    mermaid_lines = ["graph TD"]
    shown_nodes = set()
    for step in steps[:50]:
        cid = step.get("concept", "")
        node = node_map.get(cid, {})
        name = node.get("name", cid).replace('"', "'")[:30]
        diff = node.get("difficulty", "intermediate")
        style_color = {"beginner": "fill:#10b981,color:#fff", "intermediate": "fill:#3b82f6,color:#fff", "advanced": "fill:#ef4444,color:#fff"}.get(diff, "fill:#3b82f6,color:#fff")
        safe_cid = cid.replace("/", "_").replace("\\", "_").replace("(", "").replace(")", "").replace(" ", "_")
        mermaid_lines.append(f'    {safe_cid}["{name}"]')
        mermaid_lines.append(f'    style {safe_cid} {style_color}')
        shown_nodes.add(cid)

    # Use actual prerequisite edges
    for e in prereq_edges:
        src = e.get("from", "")
        tgt = e.get("to", "")
        if src in shown_nodes and tgt in shown_nodes:
            safe_src = src.replace("/", "_").replace("\\", "_").replace("(", "").replace(")", "").replace(" ", "_")
            safe_tgt = tgt.replace("/", "_").replace("\\", "_").replace("(", "").replace(")", "").replace(" ", "_")
            mermaid_lines.append(f"    {safe_src} --> {safe_tgt}")

    mermaid_chart = "\n".join(mermaid_lines)

    # Build grouped step list with progress tracking
    group_html = ""
    for group_name, group_steps in groups.items():
        if not group_steps:
            continue
        group_color = {"入门": "green", "基础": "blue", "进阶": "amber", "高级": "red"}.get(group_name, "blue")
        steps_html = ""
        for step in group_steps:
            cid = step.get("concept", "")
            node = node_map.get(cid, {})
            action = step.get("action", "learn")
            priority = step.get("priority", "normal")
            name = node.get("name", cid)
            diff = node.get("difficulty", "intermediate")
            safe_cid = _safe_filename(cid)

            action_badge = {
                "continue": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
                "fill_gap": "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
                "learn": "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
                "review": "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
            }.get(action, "bg-blue-100 text-blue-800")
            priority_icon = "🔥" if priority == "high" else ""
            importance = node.get("importance", 0.5)

            steps_html += f"""
            <div class="flex items-center gap-3 p-3 rounded-lg bg-white dark:bg-gray-800 shadow-sm step-item" data-concept="{_esc(cid)}">
                <input type="checkbox" class="step-check w-5 h-5 rounded flex-shrink-0" data-cid="{_esc(cid)}" onchange="toggleStep(this)">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                        <a href="knowledge/{safe_cid}.html" class="font-medium text-sm dark:text-white hover:text-blue-600 dark:hover:text-blue-400 truncate">{_esc(name)}</a>
                        {priority_icon}
                        <span class="px-1.5 py-0.5 rounded text-xs {action_badge}">{action}</span>
                        <span class="px-1.5 py-0.5 rounded text-xs {_difficulty_color(diff)}">{diff}</span>
                    </div>
                </div>
            </div>"""

        group_html += f"""
        <details open class="mb-4">
            <summary class="text-lg font-semibold dark:text-white cursor-pointer py-2 flex items-center gap-2">
                <span class="w-3 h-3 rounded-full bg-{group_color}-500"></span>
                {group_name} ({len(group_steps)} 个)
            </summary>
            <div class="space-y-2 ml-2">{steps_html}</div>
        </details>"""

    total = len(steps)

    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>学习路径 - OpenLearning</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/mermaid@10/dist/mermaid.min.js"></script>
    <script>tailwind.config = {{ darkMode: 'class' }}</script>
</head>
<body class="bg-gray-50 dark:bg-gray-900 transition-colors">
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div class="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <a href="index.html" class="text-blue-600 dark:text-blue-400 hover:underline">← 返回</a>
                <h1 class="text-xl font-bold dark:text-white">学习路径</h1>
            </div>
            <button onclick="document.documentElement.classList.toggle('dark'); reinitMermaid()" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl">🌓</button>
        </div>
    </header>
    <main class="max-w-4xl mx-auto px-4 py-8">
        <!-- 进度条 -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-6">
            <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium dark:text-white">学习进度</span>
                <span id="progress-text" class="text-sm text-gray-500 dark:text-gray-400">0/{total}</span>
            </div>
            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                <div id="progress-bar" class="bg-blue-600 h-3 rounded-full transition-all" style="width:0%"></div>
            </div>
        </div>

        <!-- Mermaid 图 (可折叠) -->
        <details class="bg-white dark:bg-gray-800 rounded-lg shadow mb-6">
            <summary class="p-4 font-semibold dark:text-white cursor-pointer">📊 路径可视化图 (点击展开)</summary>
            <div class="p-4 pt-0 overflow-x-auto">
                <div class="mermaid">{mermaid_chart}</div>
            </div>
        </details>

        <!-- 分组步骤列表 -->
        {group_html}
    </main>
    <script>
        const totalSteps = {total};

        // Progress tracking
        function getProgress() {{
            return JSON.parse(localStorage.getItem('openlearning_progress') || '{{}}');
        }}

        function toggleStep(checkbox) {{
            const progress = getProgress();
            const cid = checkbox.dataset.cid;
            if (checkbox.checked) {{
                progress[cid] = Date.now();
            }} else {{
                delete progress[cid];
            }}
            localStorage.setItem('openlearning_progress', JSON.stringify(progress));
            updateProgressBar();
        }}

        function updateProgressBar() {{
            const progress = getProgress();
            const done = Object.keys(progress).length;
            const pct = totalSteps > 0 ? Math.round(done / totalSteps * 100) : 0;
            document.getElementById('progress-bar').style.width = pct + '%';
            document.getElementById('progress-text').textContent = done + '/' + totalSteps;
        }}

        // Restore progress
        function restoreProgress() {{
            const progress = getProgress();
            document.querySelectorAll('.step-check').forEach(cb => {{
                if (progress[cb.dataset.cid]) {{
                    cb.checked = true;
                }}
            }});
            updateProgressBar();
        }}

        function reinitMermaid() {{
            const theme = document.documentElement.classList.contains('dark') ? 'dark' : 'default';
            mermaid.initialize({{ startOnLoad: false, theme: theme }});
            document.querySelectorAll('.mermaid').forEach(el => {{
                el.removeAttribute('data-processed');
                el.innerHTML = el.getAttribute('data-original') || el.innerHTML;
            }});
            mermaid.run();
        }}

        restoreProgress();
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
</body>
</html>"""


def _builtin_concept_page(node: dict, edges: list, res_map: dict, site_config, prev_node=None, next_node=None) -> str:
    """Generate a rich concept detail page with edge reasons, prev/next nav."""
    concept_id = node.get("id", "")
    concept_name = node.get("name", "")
    related_edges = [e for e in edges if e.get("from") == concept_id or e.get("to") == concept_id]

    prereqs = [e for e in related_edges if e.get("type") == "prerequisite" and e.get("to") == concept_id]
    extends = [e for e in related_edges if e.get("type") == "prerequisite" and e.get("from") == concept_id]
    related = [e for e in related_edges if e.get("type") == "related"]

    # Rich content fields
    definition = node.get("definition", "")
    explanation = node.get("explanation", "")
    key_points = node.get("key_points", [])
    examples = node.get("examples", [])
    common_mistakes = node.get("common_mistakes", [])
    learning_tips = node.get("learning_tips", "")
    importance = node.get("importance", 0.5)
    matched_resources = res_map.get(concept_id, [])

    # Build sections
    sections = []

    # Definition (skip if empty or placeholder)
    if definition and definition != "暂无定义":
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">\U0001f4d6 定义</h2><p class="text-gray-700 dark:text-gray-300 leading-relaxed">{_esc(definition)}</p></div>')

    # Importance badge
    stars = _importance_stars(importance)
    sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-6 flex items-center gap-4"><span class="text-sm text-gray-500 dark:text-gray-400">重要度:</span><span class="text-yellow-500">{stars}</span><span class="text-sm text-gray-500 dark:text-gray-400">({importance:.1f}/1.0)</span></div>')

    if explanation:
        paragraphs = [p.strip() for p in explanation.split("\n") if p.strip()]
        explanation_html = "".join(f'<p class="text-gray-700 dark:text-gray-300 mb-3 leading-relaxed">{_esc(p)}</p>' for p in paragraphs)
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">\U0001f4a1 详解</h2>{explanation_html}</div>')

    if key_points:
        flat = [p for item in key_points for p in (item if isinstance(item, list) else [item])]
        items = "".join(f'<li class="flex items-start gap-2"><span class="text-blue-500 mt-1">•</span><span class="text-gray-700 dark:text-gray-300">{_esc(p)}</span></li>' for p in flat if p)
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">\U0001f3af 关键要点</h2><ul class="space-y-2">{items}</ul></div>')

    if examples:
        flat = [e for item in examples for e in (item if isinstance(item, list) else [item])]
        items = "".join(f'<div class="flex items-start gap-2 mb-2"><span class="text-green-500 mt-1 font-mono">▸</span><span class="text-gray-700 dark:text-gray-300">{_esc(e)}</span></div>' for e in flat if e)
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">\U0001f527 实例</h2>{items}</div>')

    if common_mistakes:
        flat = [m for item in common_mistakes for m in (item if isinstance(item, list) else [item])]
        items = "".join(f'<li class="flex items-start gap-2"><span class="text-red-500 mt-1">⚠</span><span class="text-gray-700 dark:text-gray-300">{_esc(m)}</span></li>' for m in flat if m)
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">⚠️ 常见误区</h2><ul class="space-y-2">{items}</ul></div>')

    if learning_tips:
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6 border-l-4 border-blue-500"><h2 class="text-lg font-semibold mb-2 dark:text-white">\U0001f4a1 学习建议</h2><p class="text-gray-700 dark:text-gray-300 italic">{_esc(learning_tips)}</p></div>')

    # Prerequisites with reason
    if prereqs:
        links = []
        for e in prereqs:
            from_id = e.get("from", "")
            reason = e.get("reason", "")
            weight = e.get("weight", 0)
            reason_html = f'<span class="text-xs text-gray-400 ml-1">({reason})</span>' if reason else ""
            weight_html = f'<span class="text-xs text-gray-400 ml-1">[{weight:.1f}]</span>' if weight else ""
            links.append(f'<a href="{_safe_filename(from_id)}.html" class="px-3 py-1 bg-red-50 text-red-700 dark:bg-red-900 dark:text-red-200 rounded hover:bg-red-100">{from_id}{reason_html}{weight_html}</a>')
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">\U0001f4cb 前置知识</h2><div class="flex flex-wrap gap-2">{"".join(links)}</div></div>')

    # Extends (concepts that this one is a prerequisite for)
    if extends:
        links = []
        for e in extends:
            to_id = e.get("to", "")
            reason = e.get("reason", "")
            reason_html = f'<span class="text-xs text-gray-400 ml-1">({reason})</span>' if reason else ""
            links.append(f'<a href="{_safe_filename(to_id)}.html" class="px-3 py-1 bg-green-50 text-green-700 dark:bg-green-900 dark:text-green-200 rounded hover:bg-green-100">{to_id}{reason_html}</a>')
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">\U0001f680 进阶方向</h2><div class="flex flex-wrap gap-2">{"".join(links)}</div></div>')

    # Related with reason and weight
    if related:
        links = []
        for e in related:
            other = e.get("to") if e.get("from") == concept_id else e.get("from")
            reason = e.get("reason", "")
            weight = e.get("weight", 0)
            reason_html = f'<span class="text-xs text-gray-400 ml-1">({reason})</span>' if reason else ""
            weight_html = f'<span class="text-xs text-gray-400 ml-1">[{weight:.1f}]</span>' if weight else ""
            links.append(f'<a href="{_safe_filename(other)}.html" class="px-3 py-1 bg-blue-50 text-blue-700 dark:bg-blue-900 dark:text-blue-200 rounded hover:bg-blue-100">{other}{reason_html}{weight_html}</a>')
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">\U0001f517 相关概念</h2><div class="flex flex-wrap gap-2">{"".join(links)}</div></div>')

    # Resources
    if matched_resources:
        items = ""
        for r in matched_resources[:5]:
            title = _esc(r.get("title", "无标题"))
            url = _esc(r.get("url", "#"))
            source = r.get("source", "")
            score = r.get("quality_score", 0)
            summary = _esc(r.get("one_line_summary", "") or r.get("summary", "")[:100])
            badge = f'<span class="px-1.5 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{source}</span>' if source else ""
            score_badge = f'<span class="px-1.5 py-0.5 rounded text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-200">★ {score:.1f}</span>' if score else ""
            summary_p = f'<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{summary}</p>' if summary else ""
            items += f"""<a href="{url}" target="_blank" rel="noopener" class="block p-3 rounded-lg border dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                <div class="flex items-center gap-2 flex-wrap"><span class="font-medium text-blue-600 dark:text-blue-400">{title}</span>{badge}{score_badge}</div>{summary_p}</a>"""
        sections.append(f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6"><h2 class="text-lg font-semibold mb-3 dark:text-white">\U0001f4da 推荐资源</h2><div class="space-y-2">{items}</div></div>')

    content_sections = "\n        ".join(sections)

    # Prev/Next navigation
    nav_html = '<div class="flex justify-between mt-8 gap-4">'
    if prev_node:
        prev_id = _safe_filename(prev_node.get("id", ""))
        prev_name = _esc(prev_node.get("name", ""))
        nav_html += f'<a href="{prev_id}.html" class="flex-1 p-3 bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-lg transition-shadow"><span class="text-xs text-gray-500">← 上一个</span><p class="font-medium dark:text-white text-sm truncate">{prev_name}</p></a>'
    else:
        nav_html += '<div class="flex-1"></div>'
    if next_node:
        next_id = _safe_filename(next_node.get("id", ""))
        next_name = _esc(next_node.get("name", ""))
        nav_html += f'<a href="{next_id}.html" class="flex-1 p-3 bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-lg transition-shadow text-right"><span class="text-xs text-gray-500">下一个 →</span><p class="font-medium dark:text-white text-sm truncate">{next_name}</p></a>'
    else:
        nav_html += '<div class="flex-1"></div>'
    nav_html += '</div>'

    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{concept_name} - OpenLearning</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>tailwind.config = {{ darkMode: 'class' }}</script>
</head>
<body class="bg-gray-50 dark:bg-gray-900 transition-colors">
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div class="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-4 flex-wrap">
                <a href="../index.html" class="text-blue-600 dark:text-blue-400 hover:underline">← 返回</a>
                <h1 class="text-xl font-bold dark:text-white">{_esc(concept_name)}</h1>
                <span class="px-2 py-1 rounded text-sm {_type_color(node.get('type', 'concept'))}">{node.get('type', 'concept')}</span>
                <span class="px-2 py-1 rounded text-sm {_difficulty_color(node.get('difficulty', 'intermediate'))}">{node.get('difficulty', 'intermediate')}</span>
            </div>
            <div class="flex items-center gap-2">
                <a href="../graph.html" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-sm hover:bg-gray-200 dark:hover:bg-gray-600" title="在图谱中查看">🗺️</a>
                <button id="bookmark-btn" onclick="toggleBookmark()" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl" title="收藏">☆</button>
                <button onclick="document.documentElement.classList.toggle('dark')" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl">\U0001f313</button>
            </div>
        </div>
    </header>
    <main class="max-w-4xl mx-auto px-4 py-8">
        {content_sections}
        {nav_html}
    </main>
    <script>
        const conceptId = '{concept_id}';
        const conceptName = '{_esc(concept_name).replace(chr(39), chr(92)+chr(39))}';
        function getBookmarks() {{ return JSON.parse(localStorage.getItem('openlearning_bookmarks') || '[]'); }}
        function toggleBookmark() {{
            let bookmarks = getBookmarks();
            const idx = bookmarks.findIndex(b => b.id === conceptId);
            if (idx >= 0) {{ bookmarks.splice(idx, 1); document.getElementById('bookmark-btn').textContent = '☆'; }}
            else {{ bookmarks.push({{ id: conceptId, name: conceptName }}); document.getElementById('bookmark-btn').textContent = '★'; }}
            localStorage.setItem('openlearning_bookmarks', JSON.stringify(bookmarks));
        }}
        if (getBookmarks().some(b => b.id === conceptId)) {{ document.getElementById('bookmark-btn').textContent = '★'; }}
    </script>
</body>
</html>"""


def _builtin_bookmarks(nodes: list, site_config) -> str:
    """Generate bookmarks.html — view and manage saved concepts."""
    nodes_json = json.dumps({n.get("id", ""): n.get("name", "") for n in nodes}, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>我的收藏 - OpenLearning</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>tailwind.config = {{ darkMode: 'class' }}</script>
</head>
<body class="bg-gray-50 dark:bg-gray-900 min-h-screen transition-colors">
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div class="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <a href="index.html" class="text-blue-600 dark:text-blue-400 hover:underline">← 返回</a>
                <h1 class="text-xl font-bold dark:text-white">⭐ 我的收藏</h1>
            </div>
            <button onclick="document.documentElement.classList.toggle('dark')" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl">🌓</button>
        </div>
    </header>
    <main class="max-w-4xl mx-auto px-4 py-8">
        <div class="flex items-center justify-between mb-6">
            <span id="count" class="text-gray-500 dark:text-gray-400"></span>
            <button onclick="clearAll()" class="px-3 py-1 rounded text-sm bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200 hover:bg-red-200">清空全部</button>
        </div>
        <div id="bookmarks-list" class="space-y-3"></div>
        <p id="empty" class="hidden text-center text-gray-500 dark:text-gray-400 py-12">暂无收藏，去 <a href="index.html" class="text-blue-600 dark:text-blue-400 hover:underline">知识图谱</a> 中收藏感兴趣的节点吧</p>
    </main>
    <script>
        const nodeNames = {nodes_json};

        function getBookmarks() {{ return JSON.parse(localStorage.getItem('openlearning_bookmarks') || '[]'); }}

        function render() {{
            const bookmarks = getBookmarks();
            const list = document.getElementById('bookmarks-list');
            const empty = document.getElementById('empty');
            const count = document.getElementById('count');

            if (bookmarks.length === 0) {{
                list.innerHTML = '';
                empty.classList.remove('hidden');
                count.textContent = '';
                return;
            }}

            empty.classList.add('hidden');
            count.textContent = bookmarks.length + ' 个收藏';
            list.innerHTML = bookmarks.map(b => {{
                const safeId = b.id.replace(/[/\\\\:*?"<>|]/g, '_');
                const name = nodeNames[b.id] || b.name || b.id;
                return '<div class="flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">' +
                    '<a href="knowledge/' + safeId + '.html" class="flex-1 font-medium dark:text-white hover:text-blue-600 dark:hover:text-blue-400">' + name + '</a>' +
                    '<button onclick="removeBookmark(\\'' + b.id.replace(/'/g, "\\\\'") + '\\')" class="text-red-500 hover:text-red-700 text-sm">移除</button>' +
                '</div>';
            }}).join('');
        }}

        function removeBookmark(id) {{
            let bookmarks = getBookmarks();
            bookmarks = bookmarks.filter(b => b.id !== id);
            localStorage.setItem('openlearning_bookmarks', JSON.stringify(bookmarks));
            render();
        }}

        function clearAll() {{
            if (confirm('确定清空所有收藏？')) {{
                localStorage.removeItem('openlearning_bookmarks');
                render();
            }}
        }}

        render();
    </script>
</body>
</html>"""


class _BuiltinLoader:
    """Fallback Jinja2 loader when template directory doesn't exist."""

    def get_template(self, name: str):
        raise FileNotFoundError(f"Template {name} not found")


# ── Tools Export ─────────────────────────────────────────────

TOOLS = [build_learning_system, preview, deploy]


def get_tools() -> list:
    return list(TOOLS)
