"""Persist Skill — database operations.

Tools: save_resource, query_db, export
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from openlearning.config import get_config


# ── Input Schemas ────────────────────────────────────────────

class SaveResourceInput(BaseModel):
    resource: dict = Field(description="要保存的资源数据")


class QueryDbInput(BaseModel):
    sql: str = Field(description="SQL 查询语句")
    params: list = Field(default_factory=list, description="查询参数")


class ExportInput(BaseModel):
    format: str = Field(description="导出格式: markdown / json / anki")
    project_id: str = Field(default="", description="项目 ID")
    filter: dict = Field(default_factory=dict, description="过滤条件")


# ── Save Resource ────────────────────────────────────────────

@tool("save_resource", args_schema=SaveResourceInput)
async def save_resource(resource: dict) -> dict[str, Any]:
    """保存资源到 SQLite 数据库。

    如果 URL 已存在则更新，否则插入新记录。
    返回 {success, id, action: "inserted"/"updated"}。
    """
    from openlearning.database import get_session, select
    from openlearning.models import Resource

    url = resource.get("url", "")
    if not url:
        return {"success": False, "error": "Missing URL"}

    with get_session() as session:
        existing = session.exec(select(Resource).where(Resource.url == url)).first()

        if existing:
            # Update
            for key in [
                "title", "summary", "quality_score", "difficulty",
                "content_hash", "key_points", "resource_type",
            ]:
                if key in resource and resource[key] is not None:
                    setattr(existing, key, resource[key])
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return {"success": True, "id": existing.id, "action": "updated"}
        else:
            # Insert
            new_resource = Resource(
                project_id=resource.get("project_id", ""),
                url=url,
                title=resource.get("title", ""),
                source=resource.get("source", "unknown"),
                resource_type=resource.get("resource_type", "article"),
                author=resource.get("author"),
                summary=resource.get("summary"),
                quality_score=resource.get("quality_score", 0.0),
                difficulty=resource.get("difficulty"),
                language=resource.get("language", "en"),
                content_hash=resource.get("content_hash"),
            )
            session.add(new_resource)
            session.commit()
            session.refresh(new_resource)
            return {"success": True, "id": new_resource.id, "action": "inserted"}


# ── Query DB ─────────────────────────────────────────────────

@tool("query_db", args_schema=QueryDbInput)
async def query_db(sql: str, params: list | None = None) -> list[dict[str, Any]]:
    """查询 SQLite 数据库。

    支持 SELECT 查询。返回结果列表。
    """
    from openlearning.database import get_engine

    engine = get_engine()
    params = params or []

    # Safety: only allow SELECT
    sql_stripped = sql.strip().upper()
    if not sql_stripped.startswith("SELECT"):
        return [{"error": "Only SELECT queries are allowed"}]

    with engine.connect() as conn:
        from sqlalchemy import text

        result = conn.execute(text(sql), params)
        columns = result.keys()
        rows = [dict(zip(columns, row)) for row in result.fetchall()]

    return rows


# ── Export ────────────────────────────────────────────────────

@tool("export", args_schema=ExportInput)
async def export_data(
    format: str,
    project_id: str = "",
    filter: dict | None = None,
) -> dict[str, Any]:
    """导出项目数据为指定格式。

    支持: markdown, json, anki。
    返回 {path, count}。
    """
    from openlearning.database import get_session, select
    from openlearning.models import Resource

    config = get_config()
    output_dir = Path(config.output_dir) / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Query resources
    with get_session() as session:
        statement = select(Resource)
        if project_id:
            statement = statement.where(Resource.project_id == project_id)
        resources = list(session.exec(statement).all())

    if format == "json":
        path = output_dir / f"{project_id or 'all'}.json"
        data = [r.model_dump() for r in resources]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))

    elif format == "markdown":
        path = output_dir / f"{project_id or 'all'}.md"
        lines = ["# OpenLearning Resources\n"]
        for r in resources:
            lines.append(f"## {r.title}\n")
            lines.append(f"- **URL**: {r.url}")
            lines.append(f"- **Source**: {r.source}")
            lines.append(f"- **Type**: {r.resource_type}")
            lines.append(f"- **Score**: {r.quality_score:.1f}/10")
            if r.summary:
                lines.append(f"\n{r.summary}\n")
            lines.append("---\n")
        path.write_text("\n".join(lines), encoding="utf-8")

    elif format == "anki":
        path = output_dir / f"{project_id or 'all'}.txt"
        lines = []
        for r in resources:
            # Anki tab-separated format: front\tback
            front = r.title
            back = f"{r.summary or ''}\n\nSource: {r.url}"
            lines.append(f"{front}\t{back}")
        path.write_text("\n".join(lines), encoding="utf-8")

    else:
        return {"error": f"Unsupported format: {format}"}

    return {"path": str(path), "count": len(resources)}


# ── Tools Export ─────────────────────────────────────────────

TOOLS = [save_resource, query_db, export_data]


def get_tools() -> list:
    return list(TOOLS)
