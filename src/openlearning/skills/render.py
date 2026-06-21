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

    生成结构: index.html, graph.html, learning-path.html, knowledge/*.html, data/*.json
    返回 {site_path, pages_generated}。
    """
    from jinja2 import Environment, FileSystemLoader

    config = get_config()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Setup Jinja2
    template_dir = Path(__file__).parent.parent / "templates"
    if template_dir.exists():
        env = Environment(loader=FileSystemLoader(str(template_dir)))
    else:
        # Fallback: use built-in templates
        env = Environment(loader=_BuiltinLoader())

    path_data = learning_path or {}
    res_map = knowledge_resources or {}
    nodes = knowledge_graph.get("nodes", [])
    edges = knowledge_graph.get("edges", [])

    pages_generated = 0

    # 1. Generate index.html
    try:
        tmpl = env.get_template("index.html")
        html = tmpl.render(
            title="OpenLearning",
            graph=knowledge_graph,
            path=path_data,
            config=config.site,
        )
    except Exception:
        html = _builtin_index(knowledge_graph, path_data, config.site)

    (out / "index.html").write_text(html, encoding="utf-8")
    pages_generated += 1

    # 2. Generate graph.html (interactive knowledge graph)
    graph_html = _builtin_graph(nodes, edges, config.site)
    (out / "graph.html").write_text(graph_html, encoding="utf-8")
    pages_generated += 1

    # 3. Generate learning-path.html
    path_html = _builtin_learning_path(path_data, nodes, config.site)
    (out / "learning-path.html").write_text(path_html, encoding="utf-8")
    pages_generated += 1

    # 4. Generate per-concept pages
    knowledge_dir = out / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)

    for node in nodes:
        concept_id = node.get("id", "")
        concept_html = _builtin_concept_page(node, edges, res_map, config.site)
        (knowledge_dir / f"{concept_id}.html").write_text(concept_html, encoding="utf-8")
        pages_generated += 1

    # 5. Generate data JSON files
    data_dir = out / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "knowledge-graph.json").write_text(
        json.dumps(knowledge_graph, ensure_ascii=False, indent=2)
    )
    (data_dir / "learning-path.json").write_text(
        json.dumps(path_data, ensure_ascii=False, indent=2)
    )

    # 6. Copy static assets
    static_src = Path(__file__).parent.parent.parent.parent / "static"
    if static_src.exists():
        static_dst = out / "static"
        if static_dst.exists():
            shutil.rmtree(static_dst)
        shutil.copytree(static_src, static_dst)

    return {
        "site_path": str(out.resolve()),
        "pages_generated": pages_generated,
    }


# ── Preview ──────────────────────────────────────────────────

@tool("preview", args_schema=PreviewInput)
async def preview(port: int = 8080) -> dict[str, Any]:
    """启动本地预览服务器。

    返回 {url, port}。
    """
    config = get_config()
    output_dir = Path(config.output_dir)

    if not output_dir.exists():
        return {"error": "No output directory found. Run build first."}

    import functools
    import http.server

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(output_dir),
    )

    # Start server in background
    import threading

    server = http.server.HTTPServer(("", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return {
        "url": f"http://localhost:{port}",
        "port": port,
        "status": "running",
    }


# ── Deploy ───────────────────────────────────────────────────

@tool("deploy", args_schema=DeployInput)
async def deploy(target: str = "local", output_dir: str = "./output/") -> dict[str, Any]:
    """部署生成的站点。

    目前支持: local (本地目录)。
    返回 {url, target}。
    """
    if target == "local":
        return {
            "url": str(Path(output_dir).resolve()),
            "target": "local",
            "status": "deployed",
        }
    else:
        return {"error": f"Unsupported deploy target: {target}"}


# ── Built-in Templates ──────────────────────────────────────

def _builtin_index(graph: dict, path: dict, site_config) -> str:
    """Generate index.html."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Prepare nodes data for search
    import json
    nodes_json = json.dumps([{"id": n.get("id",""), "name": n.get("name",""), "type": n.get("type","concept"), "difficulty": n.get("difficulty","intermediate")} for n in nodes])

    # Difficulty filter buttons
    difficulties = sorted(set(n.get("difficulty", "intermediate") for n in nodes))
    diff_buttons = '<button onclick="filterNodes(\'all\')" class="filter-btn px-3 py-1 rounded-full text-sm bg-blue-600 text-white">全部</button>'
    for d in difficulties:
        diff_buttons += f'<button onclick="filterNodes(\'{d}\')" class="filter-btn px-3 py-1 rounded-full text-sm bg-gray-200 dark:bg-gray-700 dark:text-gray-200">{d}</button>'

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
            <button onclick="document.documentElement.classList.toggle('dark')" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl">🌓</button>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-8">
        <!-- 搜索框 -->
        <div class="mb-8">
            <input id="search-input" type="text" placeholder="搜索知识点..." class="w-full max-w-md px-4 py-2 rounded-lg border dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none">
        </div>

        <!-- 统计卡片 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
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

        <!-- 快捷入口 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <a href="graph.html" class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold mb-2 dark:text-white">🗺️ 知识图谱</h2>
                <p class="text-gray-600 dark:text-gray-400">交互式知识图谱，全局视角理解知识结构</p>
            </a>
            <a href="learning-path.html" class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold mb-2 dark:text-white">📚 学习路径</h2>
                <p class="text-gray-600 dark:text-gray-400">个性化学习路径，循序渐进掌握知识</p>
            </a>
        </div>

        <!-- 筛选器 -->
        <div class="flex flex-wrap gap-2 mb-4">
            {diff_buttons}
        </div>

        <!-- 知识点列表 -->
        <section>
            <h2 class="text-xl font-semibold mb-4 dark:text-white">知识点列表</h2>
            <div id="nodes-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {"".join(f'''
                <a href="knowledge/{n.get("id", "")}.html" class="node-card bg-white dark:bg-gray-800 rounded-lg shadow p-4 hover:shadow-lg transition-shadow" data-difficulty="{n.get('difficulty', 'intermediate')}">
                    <h3 class="font-semibold dark:text-white">{n.get("name", "")}</h3>
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{n.get("type", "concept")} · {n.get("difficulty", "intermediate")}</p>
                </a>
                ''' for n in nodes[:20])}
            </div>
            <p id="no-results" class="hidden text-gray-500 dark:text-gray-400 text-center py-8">未找到匹配的知识点</p>
        </section>
    </main>

    <script>
        // Fuse.js 搜索
        const nodesData = {nodes_json};
        const fuse = new Fuse(nodesData, {{ keys: ['name', 'type'], threshold: 0.4 }});

        document.getElementById('search-input').addEventListener('input', function(e) {{
            const query = e.target.value.trim();
            const cards = document.querySelectorAll('.node-card');
            const noResults = document.getElementById('no-results');

            if (!query) {{
                cards.forEach(c => c.style.display = '');
                noResults.classList.add('hidden');
                return;
            }}

            const results = fuse.search(query).map(r => r.item.id);
            let shown = 0;
            cards.forEach(card => {{
                const href = card.getAttribute('href').replace('knowledge/', '').replace('.html', '');
                if (results.includes(href)) {{
                    card.style.display = '';
                    shown++;
                }} else {{
                    card.style.display = 'none';
                }}
            }});

            noResults.classList.toggle('hidden', shown > 0);
        }});

        // 难度筛选
        function filterNodes(difficulty) {{
            const cards = document.querySelectorAll('.node-card');
            cards.forEach(card => {{
                if (difficulty === 'all' || card.dataset.difficulty === difficulty) {{
                    card.style.display = '';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
            // 更新按钮样式
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                btn.classList.remove('bg-blue-600', 'text-white');
                btn.classList.add('bg-gray-200', 'dark:bg-gray-700');
            }});
            event.target.classList.remove('bg-gray-200', 'dark:bg-gray-700');
            event.target.classList.add('bg-blue-600', 'text-white');
        }}
    </script>
</body>
</html>"""


def _builtin_graph(nodes: list, edges: list, site_config) -> str:
    """Generate graph.html with Cytoscape.js and dark mode."""
    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知识图谱 - OpenLearning</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/cytoscape@3.28.0/dist/cytoscape.min.js"></script>
    <script>tailwind.config = {{ darkMode: 'class' }}</script>
</head>
<body class="bg-gray-50 dark:bg-gray-900 transition-colors">
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <a href="index.html" class="text-blue-600 dark:text-blue-400 hover:underline">← 返回</a>
                <h1 class="text-xl font-bold dark:text-white">知识图谱</h1>
            </div>
            <button onclick="document.documentElement.classList.toggle('dark'); updateTheme()" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl">🌓</button>
        </div>
    </header>
    <div id="cy" style="width: 100%; height: calc(100vh - 80px);"></div>
    <script>
        const nodes = {json.dumps(nodes, ensure_ascii=False)};
        const edges = {json.dumps(edges, ensure_ascii=False)};

        const cy = cytoscape({{
            container: document.getElementById('cy'),
            elements: [
                ...nodes.map(n => ({{ data: {{ id: n.id, label: n.name, type: n.type }} }})),
                ...edges.map(e => ({{ data: {{ source: e.from, target: e.to, type: e.type }} }})),
            ],
            style: [
                {{ selector: 'node', style: {{ label: 'data(label)', 'background-color': '#3B82F6', color: '#fff', 'text-valign': 'center', 'font-size': '12px', width: 40, height: 40 }} }},
                {{ selector: 'node[type="principle"]', style: {{ 'background-color': '#10B981' }} }},
                {{ selector: 'node[type="technology"]', style: {{ 'background-color': '#F59E0B' }} }},
                {{ selector: 'edge', style: {{ width: 2, 'line-color': '#94A3B8', 'target-arrow-color': '#94A3B8', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier' }} }},
                {{ selector: 'edge[type="prerequisite"]', style: {{ 'line-color': '#EF4444', 'target-arrow-color': '#EF4444', 'line-style': 'dashed' }} }},
            ],
            layout: {{ name: 'breadthfirst', directed: true, spacingFactor: 1.5 }},
        }});

        cy.on('tap', 'node', function(evt) {{
            const id = evt.target.id();
            window.location.href = 'knowledge/' + id + '.html';
        }});

        function updateTheme() {{
            const isDark = document.documentElement.classList.contains('dark');
            cy.style().selector('node').style({{
                'background-color': isDark ? '#60A5FA' : '#3B82F6',
                'color': isDark ? '#1F2937' : '#fff'
            }}).update();
        }}
    </script>
</body>
</html>"""


def _builtin_learning_path(path: dict, nodes: list, site_config) -> str:
    """Generate learning-path.html with Mermaid visualization."""
    steps = path.get("steps", [])
    node_map = {n["id"]: n for n in nodes}

    # Build Mermaid flowchart
    mermaid_lines = ["graph TD"]
    for i, step in enumerate(steps):
        concept_id = step.get("concept", "")
        node = node_map.get(concept_id, {})
        name = node.get("name", concept_id).replace('"', "'")
        action = step.get("action", "learn")
        style = {
            "learn": "fill:#3b82f6,color:#fff",
            "continue": "fill:#f59e0b,color:#fff",
            "fill_gap": "fill:#ef4444,color:#fff",
            "review": "fill:#6b7280,color:#fff",
        }.get(action, "fill:#3b82f6,color:#fff")
        mermaid_lines.append(f'    {concept_id}["{name}"]')
        mermaid_lines.append(f'    style {concept_id} {style}')

    # Add edges between sequential steps
    for i in range(len(steps) - 1):
        curr = steps[i].get("concept", "")
        next_c = steps[i + 1].get("concept", "")
        if curr and next_c:
            mermaid_lines.append(f"    {curr} --> {next_c}")

    mermaid_chart = "\n".join(mermaid_lines)

    # Build step list
    steps_html = ""
    for i, step in enumerate(steps):
        concept_id = step.get("concept", "")
        node = node_map.get(concept_id, {})
        action = step.get("action", "learn")
        action_colors = {
            "continue": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
            "fill_gap": "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
            "learn": "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
            "review": "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
        }
        color = action_colors.get(action, action_colors["learn"])

        steps_html += f"""
        <div class="flex items-start gap-4 step-card" data-action="{action}">
            <div class="flex-shrink-0 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold">{i + 1}</div>
            <div class="flex-1 bg-white dark:bg-gray-800 rounded-lg shadow p-4">
                <div class="flex items-center gap-2">
                    <h3 class="font-semibold dark:text-white">{node.get('name', concept_id)}</h3>
                    <span class="px-2 py-0.5 rounded text-xs {color}">{action}</span>
                </div>
                <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{node.get('type', 'concept')} · {node.get('difficulty', 'intermediate')}</p>
                <a href="knowledge/{concept_id}.html" class="text-blue-600 dark:text-blue-400 text-sm hover:underline mt-2 inline-block">查看详情 →</a>
            </div>
        </div>"""

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
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <a href="index.html" class="text-blue-600 dark:text-blue-400 hover:underline">← 返回</a>
                <h1 class="text-xl font-bold dark:text-white">学习路径</h1>
            </div>
            <button onclick="document.documentElement.classList.toggle('dark')" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700">
                🌓
            </button>
        </div>
    </header>
    <main class="max-w-4xl mx-auto px-4 py-8">
        <!-- Mermaid 图 -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-8">
            <h2 class="text-lg font-semibold mb-4 dark:text-white">学习路径图</h2>
            <div class="mermaid">{mermaid_chart}</div>
        </div>

        <!-- 步骤列表 -->
        <h2 class="text-lg font-semibold mb-4 dark:text-white">详细步骤</h2>
        <div class="space-y-4">
            {steps_html if steps_html else '<p class="text-gray-500">暂无学习路径数据</p>'}
        </div>
    </main>
    <script>mermaid.initialize({{ startOnLoad: true, theme: 'default' }});</script>
</body>
</html>"""


def _builtin_concept_page(node: dict, edges: list, res_map: dict, site_config) -> str:
    """Generate a concept detail page with dark mode and bookmark."""
    concept_id = node.get("id", "")
    concept_name = node.get("name", "")
    related_edges = [e for e in edges if e.get("from") == concept_id or e.get("to") == concept_id]

    prereqs = [e for e in related_edges if e.get("type") == "prerequisite" and e.get("to") == concept_id]
    extends = [e for e in related_edges if e.get("type") == "extends" and e.get("from") == concept_id]
    related = [e for e in related_edges if e.get("type") == "related"]

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
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <a href="../index.html" class="text-blue-600 dark:text-blue-400 hover:underline">← 返回</a>
                <h1 class="text-xl font-bold dark:text-white">{concept_name}</h1>
                <span class="px-2 py-1 rounded text-sm bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">{node.get('type', 'concept')}</span>
                <span class="px-2 py-1 rounded text-sm bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200">{node.get('difficulty', 'intermediate')}</span>
            </div>
            <div class="flex items-center gap-2">
                <button id="bookmark-btn" onclick="toggleBookmark()" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl" title="收藏">☆</button>
                <button onclick="document.documentElement.classList.toggle('dark')" class="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-xl">🌓</button>
            </div>
        </div>
    </header>
    <main class="max-w-4xl mx-auto px-4 py-8">
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <h2 class="text-lg font-semibold mb-2 dark:text-white">定义</h2>
            <p class="text-gray-700 dark:text-gray-300">{node.get('definition', '暂无定义')}</p>
        </div>

        {f"""<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <h2 class="text-lg font-semibold mb-2 dark:text-white">前置知识</h2>
            <div class="flex flex-wrap gap-2">
                {"".join(f'<a href="{e.get("from", "")}.html" class="px-3 py-1 bg-red-50 text-red-700 dark:bg-red-900 dark:text-red-200 rounded hover:bg-red-100">{e.get("from", "")}</a>' for e in prereqs)}
            </div>
        </div>""" if prereqs else ""}

        {f"""<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <h2 class="text-lg font-semibold mb-2 dark:text-white">进阶方向</h2>
            <div class="flex flex-wrap gap-2">
                {"".join(f'<a href="{e.get("to", "")}.html" class="px-3 py-1 bg-green-50 text-green-700 dark:bg-green-900 dark:text-green-200 rounded hover:bg-green-100">{e.get("to", "")}</a>' for e in extends)}
            </div>
        </div>""" if extends else ""}

        {f"""<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h2 class="text-lg font-semibold mb-2 dark:text-white">相关概念</h2>
            <div class="flex flex-wrap gap-2">
                {"".join(f'<a href="{(e.get("to") if e.get("from") == concept_id else e.get("from"))}.html" class="px-3 py-1 bg-blue-50 text-blue-700 dark:bg-blue-900 dark:text-blue-200 rounded hover:bg-blue-100">{(e.get("to") if e.get("from") == concept_id else e.get("from"))}</a>' for e in related)}
            </div>
        </div>""" if related else ""}
    </main>
    <script>
        const conceptId = '{concept_id}';
        const conceptName = '{concept_name}';

        // 收藏功能
        function getBookmarks() {{
            return JSON.parse(localStorage.getItem('openlearning_bookmarks') || '[]');
        }}

        function toggleBookmark() {{
            let bookmarks = getBookmarks();
            const idx = bookmarks.findIndex(b => b.id === conceptId);
            if (idx >= 0) {{
                bookmarks.splice(idx, 1);
                document.getElementById('bookmark-btn').textContent = '☆';
            }} else {{
                bookmarks.push({{ id: conceptId, name: conceptName }});
                document.getElementById('bookmark-btn').textContent = '★';
            }}
            localStorage.setItem('openlearning_bookmarks', JSON.stringify(bookmarks));
        }}

        // 初始化收藏状态
        if (getBookmarks().some(b => b.id === conceptId)) {{
            document.getElementById('bookmark-btn').textContent = '★';
        }}
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
