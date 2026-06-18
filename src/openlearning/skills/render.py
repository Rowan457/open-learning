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

    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenLearning - 知识图谱学习系统</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://unpkg.com/lucide-static@latest/font/lucide.min.css">
</head>
<body class="bg-gray-50 min-h-screen">
    <header class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 py-4">
            <h1 class="text-2xl font-bold text-gray-900">OpenLearning</h1>
            <p class="text-gray-600 mt-1">知识图谱驱动的智能学习系统</p>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-8">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold text-gray-700">知识点</h3>
                <p class="text-3xl font-bold text-blue-600">{len(nodes)}</p>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold text-gray-700">关联关系</h3>
                <p class="text-3xl font-bold text-green-600">{len(edges)}</p>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold text-gray-700">学习路径</h3>
                <p class="text-3xl font-bold text-purple-600">{len(path.get('steps', []))} 步</p>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <a href="graph.html" class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold mb-2">🗺️ 知识图谱</h2>
                <p class="text-gray-600">交互式知识图谱，全局视角理解知识结构</p>
            </a>
            <a href="learning-path.html" class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold mb-2">📚 学习路径</h2>
                <p class="text-gray-600">个性化学习路径，循序渐进掌握知识</p>
            </a>
        </div>

        <section class="mt-8">
            <h2 class="text-xl font-semibold mb-4">知识点列表</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {"".join(f'''
                <a href="knowledge/{n.get("id", "")}.html" class="bg-white rounded-lg shadow p-4 hover:shadow-lg transition-shadow">
                    <h3 class="font-semibold">{n.get("name", "")}</h3>
                    <p class="text-sm text-gray-500 mt-1">{n.get("type", "concept")} · {n.get("difficulty", "intermediate")}</p>
                </a>
                ''' for n in nodes[:20])}
            </div>
        </section>
    </main>
</body>
</html>"""


def _builtin_graph(nodes: list, edges: list, site_config) -> str:
    """Generate graph.html with Cytoscape.js."""
    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知识图谱 - OpenLearning</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/cytoscape@3.28.0/dist/cytoscape.min.js"></script>
</head>
<body class="bg-gray-50">
    <header class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center gap-4">
            <a href="index.html" class="text-blue-600 hover:underline">← 返回</a>
            <h1 class="text-xl font-bold">知识图谱</h1>
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
    </script>
</body>
</html>"""


def _builtin_learning_path(path: dict, nodes: list, site_config) -> str:
    """Generate learning-path.html."""
    steps = path.get("steps", [])
    node_map = {n["id"]: n for n in nodes}

    steps_html = ""
    for i, step in enumerate(steps):
        concept_id = step.get("concept", "")
        node = node_map.get(concept_id, {})
        action = step.get("action", "learn")
        action_colors = {
            "continue": "bg-yellow-100 text-yellow-800",
            "fill_gap": "bg-red-100 text-red-800",
            "learn": "bg-blue-100 text-blue-800",
            "review": "bg-gray-100 text-gray-800",
        }
        color = action_colors.get(action, "bg-blue-100 text-blue-800")

        steps_html += f"""
        <div class="flex items-start gap-4">
            <div class="flex-shrink-0 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold">{i + 1}</div>
            <div class="flex-1 bg-white rounded-lg shadow p-4">
                <div class="flex items-center gap-2">
                    <h3 class="font-semibold">{node.get('name', concept_id)}</h3>
                    <span class="px-2 py-0.5 rounded text-xs {color}">{action}</span>
                </div>
                <p class="text-sm text-gray-500 mt-1">{node.get('type', 'concept')} · {node.get('difficulty', 'intermediate')}</p>
                <a href="knowledge/{concept_id}.html" class="text-blue-600 text-sm hover:underline mt-2 inline-block">查看详情 →</a>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>学习路径 - OpenLearning</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <header class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center gap-4">
            <a href="index.html" class="text-blue-600 hover:underline">← 返回</a>
            <h1 class="text-xl font-bold">学习路径</h1>
        </div>
    </header>
    <main class="max-w-3xl mx-auto px-4 py-8">
        <div class="space-y-6">
            {steps_html if steps_html else '<p class="text-gray-500">暂无学习路径数据</p>'}
        </div>
    </main>
</body>
</html>"""


def _builtin_concept_page(node: dict, edges: list, res_map: dict, site_config) -> str:
    """Generate a concept detail page."""
    concept_id = node.get("id", "")
    related_edges = [e for e in edges if e.get("from") == concept_id or e.get("to") == concept_id]

    prereqs = [e for e in related_edges if e.get("type") == "prerequisite" and e.get("to") == concept_id]
    extends = [e for e in related_edges if e.get("type") == "extends" and e.get("from") == concept_id]
    related = [e for e in related_edges if e.get("type") == "related"]

    return f"""<!DOCTYPE html>
<html lang="{site_config.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{node.get('name', '')} - OpenLearning</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <header class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center gap-4">
            <a href="../index.html" class="text-blue-600 hover:underline">← 返回</a>
            <h1 class="text-xl font-bold">{node.get('name', '')}</h1>
            <span class="px-2 py-1 rounded text-sm bg-blue-100 text-blue-800">{node.get('type', 'concept')}</span>
            <span class="px-2 py-1 rounded text-sm bg-gray-100 text-gray-700">{node.get('difficulty', 'intermediate')}</span>
        </div>
    </header>
    <main class="max-w-4xl mx-auto px-4 py-8">
        <div class="bg-white rounded-lg shadow p-6 mb-6">
            <h2 class="text-lg font-semibold mb-2">定义</h2>
            <p class="text-gray-700">{node.get('definition', '暂无定义')}</p>
        </div>

        {f"""<div class="bg-white rounded-lg shadow p-6 mb-6">
            <h2 class="text-lg font-semibold mb-2">前置知识</h2>
            <div class="flex flex-wrap gap-2">
                {"".join(f'<a href="{e.get("from", "")}.html" class="px-3 py-1 bg-red-50 text-red-700 rounded hover:bg-red-100">{e.get("from", "")}</a>' for e in prereqs)}
            </div>
        </div>""" if prereqs else ""}

        {f"""<div class="bg-white rounded-lg shadow p-6 mb-6">
            <h2 class="text-lg font-semibold mb-2">进阶方向</h2>
            <div class="flex flex-wrap gap-2">
                {"".join(f'<a href="{e.get("to", "")}.html" class="px-3 py-1 bg-green-50 text-green-700 rounded hover:bg-green-100">{e.get("to", "")}</a>' for e in extends)}
            </div>
        </div>""" if extends else ""}

        {f"""<div class="bg-white rounded-lg shadow p-6">
            <h2 class="text-lg font-semibold mb-2">相关概念</h2>
            <div class="flex flex-wrap gap-2">
                {"".join(f'<a href="{(e.get("to") if e.get("from") == concept_id else e.get("from"))}.html" class="px-3 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100">{(e.get("to") if e.get("from") == concept_id else e.get("from"))}</a>' for e in related)}
            </div>
        </div>""" if related else ""}
    </main>
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
