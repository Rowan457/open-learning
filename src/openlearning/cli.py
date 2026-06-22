"""CLI entry point — Typer-based command line interface."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from openlearning.config import get_config, load_config

app = typer.Typer(
    name="openlearning",
    help="OpenLearning — AI 驱动的个人学习信息系统",
    add_completion=False,
)
console = Console()


# ── Project Management ───────────────────────────────────────

@app.command()
def init(
    topic: str = typer.Argument("", help="学习主题 (留空则进入对话模式)"),
    level: str = typer.Option("", "--level", "-l", help="难度: beginner/intermediate/advanced"),
    lang: str = typer.Option("", "--lang", help="语言偏好: zh,en"),
    from_file: Optional[str] = typer.Option(None, "--from-file", help="从配置文件创建"),
    skip_chat: bool = typer.Option(False, "--skip-chat", "-y", help="跳过对话，直接使用默认值"),
):
    """创建新的学习项目。支持对话式主题确认。"""
    from openlearning.database import create_project, init_db

    console.print(Panel(f"[bold blue]OpenLearning[/] — 创建学习项目", subtitle="v0.1.0"))

    # 对话模式：通过问答确定学习需求
    if not skip_chat:
        profile = _chat_collect_info(topic)
    else:
        profile = {
            "topic": topic,
            "level": level or "beginner",
            "languages": lang.split(",") if lang else ["zh", "en"],
            "goal": "",
            "background": "",
            "resource_types": ["article", "video", "paper", "repo"],
        }

    if not profile.get("topic"):
        console.print("[red]未指定学习主题[/]")
        raise typer.Exit(1)

    # Initialize database
    init_db()

    # Create project
    desc_parts = []
    if profile.get("goal"):
        desc_parts.append(f"目标: {profile['goal']}")
    if profile.get("background"):
        desc_parts.append(f"基础: {profile['background']}")
    desc_parts.append(f"难度: {profile.get('level', 'beginner')}")
    desc_parts.append(f"语言: {','.join(profile.get('languages', ['zh', 'en']))}")

    project = create_project(
        title=profile["topic"],
        description=" | ".join(desc_parts),
    )

    console.print(f"\n[green]✓[/] 项目已创建: [bold]{project.title}[/]")
    console.print(f"  ID: {project.id}")
    console.print(f"  描述: {project.description}")

    # Ask if user wants to start collecting
    if typer.confirm("\n立即开始采集资源?"):
        _run_collect(
            project.id,
            profile["topic"],
            profile.get("level", "beginner"),
            profile.get("languages", ["zh", "en"]),
            user_profile=profile,
        )


def _chat_collect_info(initial_topic: str = "") -> dict:
    """对话式收集学习需求。"""
    console.print("\n[bold]📋 了解你的学习需求[/]\n")

    # 1. 学习主题
    topic = initial_topic
    if not topic:
        topic = console.input("[bold]你想学什么？[/] ").strip()
    else:
        console.print(f"[bold]学习主题:[/] {topic}")

    # 2. 学习目标
    console.print("\n[bold]你希望学到什么程度？[/]")
    console.print("  例如：能独立开发项目 / 理解核心概念 / 通过面试 / 解决实际问题")
    goal = console.input("[bold]学习目标[/] (可选，回车跳过): ").strip()

    # 3. 已有基础
    console.print(f"\n[bold]你目前有什么相关基础？[/]")
    console.print("  例如：有 Python 经验 / 完全零基础 / 学过一些理论")
    background = console.input("[bold]基础情况[/] (可选，回车跳过): ").strip()

    # 4. 难度偏好
    level = "beginner"
    if background:
        # 根据基础自动推荐难度
        bg_lower = background.lower()
        if any(w in bg_lower for w in ["精通", "熟练", "多年", "expert", "senior"]):
            level = "advanced"
        elif any(w in bg_lower for w in ["学过", "了解", "用过", "有基础", "intermediate"]):
            level = "intermediate"

    console.print(f"\n[bold]推荐难度:[/] {level}")
    override = console.input("[bold]难度[/] (beginner/intermediate/advanced，回车使用推荐): ").strip()
    if override in ("beginner", "intermediate", "advanced"):
        level = override

    # 5. 资源偏好
    console.print("\n[bold]你偏好什么类型的学习资源？[/]")
    console.print("  [dim]1[/] 文章/教程  [dim]2[/] 视频  [dim]3[/] 论文  [dim]4[/] 代码仓库  [dim]5[/] 全部")
    type_input = console.input("[bold]选择[/] (可多选如 1,2,5，回车=全部): ").strip()

    type_map = {"1": "article", "2": "video", "3": "paper", "4": "repo"}
    if not type_input or "5" in type_input:
        resource_types = ["article", "video", "paper", "repo"]
    else:
        resource_types = [type_map[c] for c in type_input.split(",") if c.strip() in type_map]
        if not resource_types:
            resource_types = ["article", "video", "paper", "repo"]

    # 6. 语言偏好
    lang_input = console.input("\n[bold]语言偏好[/] (zh,en / zh / en，回车=中英文): ").strip()
    languages = [l.strip() for l in lang_input.split(",") if l.strip()] if lang_input else ["zh", "en"]

    # 确认
    console.print("\n" + "─" * 40)
    console.print("[bold]📋 学习需求确认[/]")
    console.print(f"  主题:     [bold]{topic}[/]")
    console.print(f"  目标:     {goal or '(未指定)'}")
    console.print(f"  基础:     {background or '(未指定)'}")
    console.print(f"  难度:     {level}")
    console.print(f"  资源类型: {', '.join(resource_types)}")
    console.print(f"  语言:     {', '.join(languages)}")
    console.print("─" * 40)

    if not typer.confirm("确认开始?"):
        console.print("[yellow]已取消[/]")
        raise typer.Exit(0)

    return {
        "topic": topic,
        "goal": goal,
        "background": background,
        "level": level,
        "resource_types": resource_types,
        "languages": languages,
    }


@app.command()
def list_projects():
    """列出所有学习项目。"""
    from openlearning.database import init_db, list_projects as db_list

    init_db()
    projects = db_list()

    if not projects:
        console.print("[yellow]暂无项目。使用 'openlearning init' 创建。[/]")
        return

    table = Table(title="学习项目")
    table.add_column("ID", style="dim")
    table.add_column("标题", style="bold")
    table.add_column("状态")
    table.add_column("创建时间")

    for p in projects:
        table.add_row(p.id, p.title, p.status, str(p.created_at)[:19])

    console.print(table)


@app.command()
def status(project_id: str = typer.Argument(..., help="项目 ID")):
    """查看项目状态。"""
    from openlearning.database import get_project, get_resources_by_project, init_db

    init_db()
    project = get_project(project_id)

    if not project:
        console.print(f"[red]未找到项目: {project_id}[/]")
        raise typer.Exit(1)

    resources = get_resources_by_project(project_id)

    console.print(Panel(f"[bold]{project.title}[/]", subtitle=f"ID: {project.id}"))
    console.print(f"  状态: {project.status}")
    console.print(f"  资源数: {len(resources)}")
    console.print(f"  创建: {project.created_at}")
    console.print(f"  更新: {project.updated_at}")

    if resources:
        scores = [r.quality_score for r in resources if r.quality_score]
        avg = sum(scores) / len(scores) if scores else 0
        console.print(f"  平均质量: {avg:.1f}/10")


# ── Resource Collection ──────────────────────────────────────

@app.command()
def collect(
    project_id: str = typer.Argument(..., help="项目 ID"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="指定数据源: google/arxiv/youtube/github"),
    dry_run: bool = typer.Option(False, "--dry-run", help="预览采集计划"),
    max_iter: int = typer.Option(2, "--max-iter", help="最大迭代轮次"),
):
    """执行资源采集。"""
    from openlearning.database import get_project, init_db

    init_db()
    project = get_project(project_id)

    if not project:
        console.print(f"[red]未找到项目: {project_id}[/]")
        raise typer.Exit(1)

    level = "beginner"
    lang = ["zh", "en"]

    if dry_run:
        console.print("[yellow]预览模式 — 不实际执行采集[/]")
        _show_dry_run(project.title, level, lang)
        return

    _run_collect(project_id, project.title, level, lang, max_iterations=max_iter)


def _run_collect(
    project_id: str,
    topic: str,
    level: str,
    lang: list[str],
    max_iterations: int = 2,
    user_profile: dict | None = None,
):
    """Run the full collection pipeline."""
    from openlearning.agents.graph import run_pipeline
    from openlearning.database import init_db

    init_db()

    # Build profile from conversation or parameters
    profile = user_profile or {}
    profile.setdefault("level", level)
    profile.setdefault("lang", lang)
    profile.setdefault("user_id", "default")

    console.print(f"\n[bold]开始采集: {topic}[/]")
    console.print(f"  难度: {level}")
    console.print(f"  语言: {', '.join(lang)}")
    if profile.get("goal"):
        console.print(f"  目标: {profile['goal']}")
    console.print(f"  最大迭代: {max_iterations}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("运行 Agent Pipeline...", total=None)

        # Run the pipeline
        try:
            result = asyncio.run(
                run_pipeline(
                    user_request=topic,
                    user_profile=profile,
                    max_iterations=max_iterations,
                )
            )
        except Exception as e:
            console.print(f"[red]Pipeline 错误: {e}[/]")
            raise typer.Exit(1)

        progress.update(task, description="采集完成!")

    # Display results
    _show_results(result)


def _show_dry_run(topic: str, level: str, lang: list[str]):
    """Show dry-run preview."""
    from openlearning.agents.planner import _analyze_request, _generate_search_queries, _expand_knowledge_graph

    analysis = _analyze_request(topic, {"level": level, "lang": lang})
    graph = _expand_knowledge_graph(analysis)
    queries = _generate_search_queries(graph, analysis, {"level": level, "lang": lang})

    console.print(f"\n[bold]主题:[/] {topic}")
    console.print(f"[bold]子主题:[/] {', '.join(analysis['subtopics'])}")
    console.print(f"\n[bold]搜索关键词 ({len(queries)} 个):[/]")
    for q in queries:
        console.print(f"  • {q}")

    console.print(f"\n[bold]知识图谱节点: {len(graph['nodes'])}[/]")


def _show_results(result: dict):
    """Display pipeline results."""
    console.print("\n" + "=" * 60)

    # Summary
    resources = result.get("analyzed_resources", [])
    graph = result.get("knowledge_graph", {})
    evaluation = result.get("evaluation", {})
    learning_system = result.get("learning_system", {})

    console.print(Panel("[bold green]采集完成[/]", subtitle="Pipeline 结果"))

    # Resources table
    if resources:
        table = Table(title="采集到的资源")
        table.add_column("#", style="dim")
        table.add_column("标题", max_width=50)
        table.add_column("来源")
        table.add_column("质量分")
        table.add_column("难度")

        for i, r in enumerate(resources[:15], 1):
            title = r.get("title", "")[:50]
            source = r.get("source", "unknown")
            score = r.get("quality_score", 0)
            diff = r.get("difficulty", "—")

            score_color = "green" if score >= 7 else "yellow" if score >= 5 else "red"
            table.add_row(
                str(i),
                title,
                source,
                f"[{score_color}]{score:.1f}[/]",
                diff or "—",
            )

        console.print(table)

    # Knowledge graph
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    console.print(f"\n[bold]知识图谱:[/] {len(nodes)} 个节点, {len(edges)} 条边")

    # Evaluation
    if evaluation:
        console.print(f"[bold]评估:[/] {'✓ 通过' if evaluation.get('pass') else '✗ 未通过'}")
        for key in ["quality", "coverage", "diversity", "freshness"]:
            check = evaluation.get(key, {})
            status = "✓" if check.get("pass") else "✗"
            console.print(f"  {status} {key}: {check.get('reason', '')}")

    # Site
    site_path = learning_system.get("site_path", "")
    if site_path:
        console.print(f"\n[bold green]学习系统已生成:[/] {site_path}")
        console.print(f"  页面数: {learning_system.get('pages_generated', 0)}")
        console.print(f"\n  打开 [bold]index.html[/] 开始学习!")


# ── Site Generation ──────────────────────────────────────────

@app.command()
def build(
    project_id: str = typer.Argument(..., help="项目 ID"),
    output: str = typer.Option("./output/", "--output", "-o", help="输出目录"),
):
    """从已有数据重新生成静态站点。"""
    import asyncio
    from pathlib import Path

    from openlearning.skills.render import build_learning_system

    data_dir = Path(output) / "data"
    kg_path = data_dir / "knowledge-graph.json"
    lp_path = data_dir / "learning-path.json"

    if not kg_path.exists():
        console.print(f"[red]未找到知识图谱数据: {kg_path}[/]")
        console.print(f"[yellow]请先运行 'openlearning collect {project_id}'[/]")
        raise typer.Exit(1)

    console.print(f"[bold]重新生成站点...[/]")

    import json

    knowledge_graph = json.loads(kg_path.read_text(encoding="utf-8"))
    learning_path = json.loads(lp_path.read_text(encoding="utf-8")) if lp_path.exists() else {}

    nodes = knowledge_graph.get("nodes", [])
    edges = knowledge_graph.get("edges", [])
    console.print(f"  知识图谱: {len(nodes)} 节点, {len(edges)} 边")

    # Build knowledge resources map from graph data
    knowledge_resources = {}
    for node in nodes:
        concept_id = node.get("id", "")
        knowledge_resources[concept_id] = []  # Resources are in the graph nodes already

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("生成站点...", total=None)
        result = asyncio.run(
            build_learning_system.ainvoke({
                "knowledge_graph": knowledge_graph,
                "learning_path": learning_path,
                "knowledge_resources": knowledge_resources,
                "output_dir": output,
            })
        )
        progress.update(task, description="生成完成!")

    console.print(f"\n[green]✓[/] 站点已生成: {result.get('site_path', output)}")
    console.print(f"  页面数: {result.get('pages_generated', 0)}")
    console.print(f"\n  打开 [bold]{output}/index.html[/] 查看!")


@app.command()
def serve(
    project_id: str = typer.Argument(..., help="项目 ID"),
    port: int = typer.Option(8080, "--port", "-p", help="端口"),
):
    """启动本地预览服务器。"""
    import functools
    import http.server
    import threading

    config = get_config()
    output_dir = Path(config.output_dir)

    if not output_dir.exists():
        console.print("[red]输出目录不存在。请先运行 'openlearning build'[/]")
        raise typer.Exit(1)

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(output_dir),
    )

    server = http.server.HTTPServer(("", port), handler)
    console.print(f"[green]预览服务器启动:[/] http://localhost:{port}")
    console.print("按 Ctrl+C 停止")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]服务器已停止[/]")


# ── Export ───────────────────────────────────────────────────

@app.command()
def export(
    project_id: str = typer.Argument(..., help="项目 ID"),
    format: str = typer.Option("markdown", "--format", "-f", help="格式: markdown/json/anki"),
):
    """导出项目数据。"""
    from openlearning.database import get_resources_by_project, init_db

    init_db()
    resources = get_resources_by_project(project_id)

    if not resources:
        console.print("[yellow]项目无资源可导出[/]")
        return

    output_dir = Path("output/exports")
    output_dir.mkdir(parents=True, exist_ok=True)

    if format == "json":
        import json

        path = output_dir / f"{project_id}.json"
        data = [{"title": r.title, "url": r.url, "score": r.quality_score} for r in resources]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    elif format == "markdown":
        path = output_dir / f"{project_id}.md"
        lines = ["# OpenLearning Resources\n"]
        for r in resources:
            lines.append(f"## {r.title}\n- URL: {r.url}\n- Score: {r.quality_score:.1f}\n")
        path.write_text("\n".join(lines), encoding="utf-8")
    else:
        console.print(f"[red]不支持的格式: {format}[/]")
        return

    console.print(f"[green]✓[/] 已导出 {len(resources)} 条资源到 {path}")


# ── Config ───────────────────────────────────────────────────

@app.command()
def config_show():
    """显示当前配置。"""
    cfg = get_config()
    console.print(Panel("[bold]OpenLearning 配置[/]"))
    console.print(f"  LLM Provider: {cfg.llm.provider}")
    console.print(f"  LLM Base URL: {cfg.llm.base_url}")
    console.print(f"  Models: pro={cfg.llm.models.pro}, standard={cfg.llm.models.standard}, lite={cfg.llm.models.lite}")
    console.print(f"  DB Path: {cfg.db_path}")
    console.print(f"  Output Dir: {cfg.output_dir}")
    console.print(f"  LangSmith: {'enabled' if cfg.langsmith.enabled else 'disabled'}")


@app.command()
def config_set(
    key: str = typer.Argument(..., help="配置键 (如 llm.models.pro)"),
    value: str = typer.Argument(..., help="配置值"),
):
    """修改配置。"""
    console.print(f"[yellow]配置修改功能开发中。请直接编辑 openlearning.yaml 或设置环境变量。[/]")


# ── Version ──────────────────────────────────────────────────

@app.command()
def version():
    """显示版本信息。"""
    from openlearning import __version__

    console.print(f"OpenLearning v{__version__}")


if __name__ == "__main__":
    app()
