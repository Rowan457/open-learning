"""FastAPI application — Web UI management panel.

Routes:
- /              → Dashboard
- /projects      → Project list
- /projects/{id} → Project detail
- /api/*         → REST API endpoints
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from openlearning.web.api import api_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OpenLearning Web UI",
        description="AI 驱动的个人学习信息系统 — 管理面板",
        version="0.1.0",
    )

    # Mount API router
    app.include_router(api_router, prefix="/api")

    # Serve static files (generated site)
    output_dir = Path("output")
    if output_dir.exists():
        app.mount("/site", StaticFiles(directory=str(output_dir), html=True), name="site")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Main dashboard page."""
        return _dashboard_html()

    @app.get("/projects", response_class=HTMLResponse)
    async def projects_page():
        """Projects list page."""
        return _projects_html()

    @app.get("/projects/{project_id}", response_class=HTMLResponse)
    async def project_detail_page(project_id: str):
        """Project detail page."""
        return _project_detail_html(project_id)

    @app.get("/plugins", response_class=HTMLResponse)
    async def plugins_page():
        """Plugins management page."""
        return _plugins_html()

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0"}

    return app


# ── HTML Templates ──────────────────────────────────────────

_BASE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - OpenLearning</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               background: #f5f5f5; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        nav {{ background: #1a1a2e; color: white; padding: 15px 20px; display: flex; align-items: center; gap: 30px; }}
        nav a {{ color: #e0e0e0; text-decoration: none; font-size: 14px; }}
        nav a:hover {{ color: white; }}
        nav .brand {{ font-size: 18px; font-weight: bold; color: #4fc3f7; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin: 15px 0;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .card h2 {{ font-size: 18px; margin-bottom: 15px; color: #1a1a2e; }}
        .stat {{ display: inline-block; text-align: center; padding: 15px 25px; }}
        .stat .value {{ font-size: 32px; font-weight: bold; color: #4fc3f7; }}
        .stat .label {{ font-size: 13px; color: #888; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ font-weight: 600; color: #555; font-size: 13px; }}
        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; }}
        .badge-green {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-yellow {{ background: #fff3e0; color: #e65100; }}
        .badge-gray {{ background: #f5f5f5; color: #888; }}
        .btn {{ display: inline-block; padding: 8px 16px; border-radius: 6px; border: none;
                cursor: pointer; font-size: 14px; text-decoration: none; }}
        .btn-primary {{ background: #4fc3f7; color: white; }}
        .btn-primary:hover {{ background: #29b6f6; }}
        .btn-danger {{ background: #ef5350; color: white; }}
        .btn-danger:hover {{ background: #e53935; }}
        .btn-sm {{ padding: 5px 12px; font-size: 12px; }}
        .empty {{ text-align: center; padding: 40px; color: #999; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .loading {{ color: #999; font-style: italic; }}
    </style>
</head>
<body>
    <nav>
        <span class="brand">OpenLearning</span>
        <a href="/">仪表盘</a>
        <a href="/projects">项目管理</a>
        <a href="/plugins">插件管理</a>
        <a href="/site/" target="_blank">查看站点</a>
    </nav>
    <div class="container">
        {content}
    </div>
    <script>
        async function api(method, path, body) {{
            const opts = {{method, headers: {{'Content-Type': 'application/json'}}}};
            if (body) opts.body = JSON.stringify(body);
            const r = await fetch('/api' + path, opts);
            return r.json();
        }}
        function badge(status) {{
            const cls = {{active:'badge-green', archived:'badge-gray', paused:'badge-yellow'}}[status] || 'badge-gray';
            return `<span class="badge ${{cls}}">${{status}}</span>`;
        }}
    </script>
</body>
</html>"""


def _dashboard_html() -> str:
    content = """
    <h1 style="margin: 20px 0;">仪表盘</h1>
    <div class="grid" id="stats">
        <div class="card"><div class="stat"><div class="value" id="project-count">-</div><div class="label">项目数</div></div></div>
        <div class="card"><div class="stat"><div class="value" id="resource-count">-</div><div class="label">资源总数</div></div></div>
        <div class="card"><div class="stat"><div class="value" id="plugin-count">-</div><div class="label">插件数</div></div></div>
        <div class="card"><div class="stat"><div class="value" id="avg-score">-</div><div class="label">平均质量</div></div></div>
    </div>
    <div class="card">
        <h2>最近项目</h2>
        <table>
            <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>资源数</th><th>操作</th></tr></thead>
            <tbody id="recent-projects"><tr><td colspan="5" class="loading">加载中...</td></tr></tbody>
        </table>
    </div>
    <script>
        async function loadDashboard() {
            const projects = await api('GET', '/projects');
            const plugins = await api('GET', '/plugins');

            let totalResources = 0, totalScore = 0, scoreCount = 0;
            const tbody = document.getElementById('recent-projects');
            tbody.innerHTML = '';

            for (const p of projects.slice(0, 5)) {
                totalResources += p.resource_count || 0;
                if (p.avg_score) { totalScore += p.avg_score; scoreCount++; }
                tbody.innerHTML += `<tr>
                    <td style="color:#888">${p.id.slice(0,8)}</td>
                    <td><a href="/projects/${p.id}">${p.title}</a></td>
                    <td>${badge(p.status)}</td>
                    <td>${p.resource_count || 0}</td>
                    <td><a href="/projects/${p.id}" class="btn btn-primary btn-sm">查看</a></td>
                </tr>`;
            }
            if (!projects.length) tbody.innerHTML = '<tr><td colspan="5" class="empty">暂无项目</td></tr>';

            document.getElementById('project-count').textContent = projects.length;
            document.getElementById('resource-count').textContent = totalResources;
            document.getElementById('plugin-count').textContent = plugins.length;
            document.getElementById('avg-score').textContent = scoreCount ? (totalScore/scoreCount).toFixed(1) : '-';
        }
        loadDashboard();
    </script>"""
    return _BASE_HTML.format(title="仪表盘", content=content)


def _projects_html() -> str:
    content = """
    <h1 style="margin: 20px 0;">项目管理</h1>
    <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h2 style="margin:0;">所有项目</h2>
            <button class="btn btn-primary" onclick="createProject()">+ 新建项目</button>
        </div>
        <table>
            <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>资源数</th><th>质量</th><th>更新时间</th><th>操作</th></tr></thead>
            <tbody id="project-list"><tr><td colspan="7" class="loading">加载中...</td></tr></tbody>
        </table>
    </div>
    <script>
        async function loadProjects() {
            const projects = await api('GET', '/projects');
            const tbody = document.getElementById('project-list');
            tbody.innerHTML = '';
            for (const p of projects) {
                tbody.innerHTML += `<tr>
                    <td style="color:#888">${p.id.slice(0,8)}</td>
                    <td><a href="/projects/${p.id}">${p.title}</a></td>
                    <td>${badge(p.status)}</td>
                    <td>${p.resource_count || 0}</td>
                    <td>${p.avg_score ? p.avg_score.toFixed(1) : '-'}</td>
                    <td>${(p.updated_at||'').slice(0,10)}</td>
                    <td>
                        <a href="/projects/${p.id}" class="btn btn-primary btn-sm">查看</a>
                        <button class="btn btn-danger btn-sm" onclick="deleteProject('${p.id}','${p.title}')">删除</button>
                    </td>
                </tr>`;
            }
            if (!projects.length) tbody.innerHTML = '<tr><td colspan="7" class="empty">暂无项目，点击"新建项目"开始</td></tr>';
        }
        async function deleteProject(id, title) {
            if (!confirm(`确认删除项目 "${{title}}"？此操作不可恢复！`)) return;
            await api('DELETE', '/projects/' + id);
            loadProjects();
        }
        async function createProject() {
            const title = prompt('请输入学习主题:');
            if (!title) return;
            await api('POST', '/projects', {title});
            loadProjects();
        }
        loadProjects();
    </script>"""
    return _BASE_HTML.format(title="项目管理", content=content)


def _project_detail_html(project_id: str) -> str:
    content = f"""
    <div id="project-header" style="margin: 20px 0;">
        <h1 class="loading">加载中...</h1>
    </div>
    <div class="grid">
        <div class="card"><div class="stat"><div class="value" id="res-count">-</div><div class="label">资源数</div></div></div>
        <div class="card"><div class="stat"><div class="value" id="quality">-</div><div class="label">平均质量</div></div></div>
        <div class="card"><div class="stat"><div class="value" id="sources">-</div><div class="label">数据源</div></div></div>
    </div>
    <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h2 style="margin:0;">资源列表</h2>
            <div>
                <button class="btn btn-primary btn-sm" onclick="collect()">采集新资源</button>
                <button class="btn btn-sm" onclick="exportProject()">导出</button>
            </div>
        </div>
        <table>
            <thead><tr><th>标题</th><th>来源</th><th>类型</th><th>质量</th><th>难度</th></tr></thead>
            <tbody id="resource-list"><tr><td colspan="5" class="loading">加载中...</td></tr></tbody>
        </table>
    </div>
    <script>
        const PID = "{project_id}";
        async function loadProject() {
            const p = await api('GET', '/projects/' + PID);
            if (p.error) {{ document.getElementById('project-header').innerHTML = '<h1>项目未找到</h1>'; return; }}
            document.getElementById('project-header').innerHTML = `<h1>${{p.title}}</h1><p style="color:#888">${{p.description||''}}</p>`;
            document.getElementById('res-count').textContent = p.resource_count || 0;
            document.getElementById('quality').textContent = p.avg_score ? p.avg_score.toFixed(1) : '-';
            const sources = p.sources || {};
            document.getElementById('sources').textContent = Object.keys(sources).length;

            const resources = await api('GET', '/projects/' + PID + '/resources');
            const tbody = document.getElementById('resource-list');
            tbody.innerHTML = '';
            for (const r of resources.slice(0, 50)) {
                const score = r.quality_score ? r.quality_score.toFixed(1) : '-';
                const sc = r.quality_score >= 7 ? 'color:#2e7d32' : r.quality_score >= 5 ? 'color:#e65100' : 'color:#c62828';
                tbody.innerHTML += `<tr>
                    <td><a href="${{r.url}}" target="_blank">${{r.title}}</a></td>
                    <td>${{r.source}}</td>
                    <td>${{r.resource_type||'-'}}</td>
                    <td style="${{sc}}">${{score}}</td>
                    <td>${{r.difficulty||'-'}}</td>
                </tr>`;
            }
            if (!resources.length) tbody.innerHTML = '<tr><td colspan="5" class="empty">暂无资源，点击"采集新资源"开始</td></tr>';
        }
        async function collect() {{
            const btn = event.target;
            btn.disabled = true; btn.textContent = '采集中...';
            await api('POST', '/projects/' + PID + '/collect');
            btn.disabled = false; btn.textContent = '采集新资源';
            loadProject();
        }}
        async function exportProject() {{
            window.open('/api/projects/' + PID + '/export?format=markdown');
        }}
        loadProject();
    </script>"""
    return _BASE_HTML.format(title="项目详情", content=content)


def _plugins_html() -> str:
    content = """
    <h1 style="margin: 20px 0;">插件管理</h1>
    <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h2 style="margin:0;">已安装插件</h2>
            <button class="btn btn-primary btn-sm" onclick="reloadPlugins()">重新加载</button>
        </div>
        <table>
            <thead><tr><th>名称</th><th>版本</th><th>描述</th><th>类型</th><th>状态</th><th>操作</th></tr></thead>
            <tbody id="plugin-list"><tr><td colspan="6" class="loading">加载中...</td></tr></tbody>
        </table>
    </div>
    <script>
        async function loadPlugins() {
            const plugins = await api('GET', '/plugins');
            const tbody = document.getElementById('plugin-list');
            tbody.innerHTML = '';
            for (const p of plugins) {
                const status = p.enabled ? '<span class="badge badge-green">启用</span>' : '<span class="badge badge-gray">禁用</span>';
                const action = p.enabled
                    ? `<button class="btn btn-sm" onclick="togglePlugin('${p.name}',false)">禁用</button>`
                    : `<button class="btn btn-primary btn-sm" onclick="togglePlugin('${p.name}',true)">启用</button>`;
                tbody.innerHTML += `<tr>
                    <td><strong>${p.name}</strong></td>
                    <td>${p.version}</td>
                    <td>${p.description}</td>
                    <td>${p.source_type}</td>
                    <td>${status}</td>
                    <td>${action}</td>
                </tr>`;
            }
            if (!plugins.length) tbody.innerHTML = '<tr><td colspan="6" class="empty">未发现插件。将 .py 文件放入 plugins/ 目录</td></tr>';
        }
        async function togglePlugin(name, enable) {
            await api('PUT', '/plugins/' + name + '/' + (enable ? 'enable' : 'disable'));
            loadPlugins();
        }
        async function reloadPlugins() {
            await api('POST', '/plugins/reload');
            loadPlugins();
        }
        loadPlugins();
    </script>"""
    return _BASE_HTML.format(title="插件管理", content=content)
