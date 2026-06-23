"""Updater Agent — incremental change detection and update orchestration.

Checks existing resources for content changes, detects new/updated/removed,
and optionally triggers re-analysis and site rebuild.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from openlearning.log import get_logger
from openlearning.skills.fetch import fetch_page

logger = get_logger("Updater")


@dataclass
class UpdateReport:
    """Summary of detected changes."""

    new: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    errors: int = 0
    details: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "new": self.new,
            "updated": self.updated,
            "removed": self.removed,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "total_checked": self.new + self.updated + self.removed + self.unchanged + self.errors,
        }

    def summary(self) -> str:
        parts = []
        if self.new:
            parts.append(f"新增 {self.new}")
        if self.updated:
            parts.append(f"更新 {self.updated}")
        if self.removed:
            parts.append(f"失效 {self.removed}")
        if self.errors:
            parts.append(f"错误 {self.errors}")
        parts.append(f"无变化 {self.unchanged}")
        return " / ".join(parts)


async def check_updates(project_id: str) -> UpdateReport:
    """Check all existing resources for content changes.

    For each resource:
    1. Re-fetch the URL
    2. Compute new content_hash (sha256 of full text)
    3. Compare with stored hash
    4. Record changes in updates table

    Returns an UpdateReport with counts.
    """
    from openlearning.database import get_resources_by_project, record_update

    resources = get_resources_by_project(project_id)
    if not resources:
        logger.info("项目 %s 无资源", project_id)
        return UpdateReport()

    logger.info("检查 %s 条资源的变更...", len(resources))
    report = UpdateReport()

    # Process in batches of 8 for concurrency
    semaphore = asyncio.Semaphore(8)

    async def _check_one(resource) -> None:
        async with semaphore:
            try:
                result = await fetch_page.ainvoke({"url": resource.url})

                if not result.get("success"):
                    report.errors += 1
                    report.details.append({
                        "url": resource.url,
                        "status": "error",
                        "error": result.get("error", "fetch failed"),
                    })
                    return

                new_hash = result.get("content_hash", "")
                old_hash = resource.content_hash or ""

                if not old_hash:
                    # First time checking — store hash, count as new
                    resource.content_hash = new_hash
                    _update_resource_hash(resource, new_hash)
                    record_update(resource.id, "new", None, new_hash)
                    report.new += 1
                    report.details.append({"url": resource.url, "status": "new"})
                elif new_hash != old_hash:
                    # Content changed
                    record_update(resource.id, "updated", old_hash, new_hash)
                    _update_resource_hash(resource, new_hash)
                    report.updated += 1
                    report.details.append({
                        "url": resource.url,
                        "status": "updated",
                        "old_hash": old_hash[:8],
                        "new_hash": new_hash[:8],
                    })
                else:
                    report.unchanged += 1

            except Exception as e:
                report.errors += 1
                report.details.append({
                    "url": resource.url,
                    "status": "error",
                    "error": str(e),
                })

    tasks = [_check_one(r) for r in resources]
    await asyncio.gather(*tasks)

    logger.info("变更检测完成: %s", report.summary())
    return report


def _update_resource_hash(resource, new_hash: str) -> None:
    """Update a resource's content_hash in the database."""
    from sqlmodel import select, Session
    from openlearning.database import get_engine
    from openlearning.models import Resource

    with Session(get_engine()) as session:
        db_resource = session.get(Resource, resource.id)
        if db_resource:
            db_resource.content_hash = new_hash
            session.add(db_resource)
            session.commit()


async def incremental_collect(project_id: str, since_days: int = 7) -> list[dict]:
    """Run incremental collection — search for new content and merge with existing.

    Uses the collector in incremental mode (skips existing URLs).
    Returns newly collected resources.
    """
    from openlearning.agents.state import AgentState
    from openlearning.agents.collector import collector_agent

    # Build a minimal state for the collector
    # We need search queries — reuse from the project's learning plan
    queries = _get_project_queries(project_id)
    if not queries:
        logger.warning("项目 %s 无搜索词, 跳过增量采集", project_id)
        return []

    state: AgentState = {
        "search_queries": queries,
        "learning_plan": {"project_id": project_id},
        "incremental": True,
        "since_days": since_days,
    }

    result = await collector_agent(state)
    new_resources = result.get("raw_resources", [])
    logger.info("增量采集: 新增 %s 条资源", len(new_resources))
    return new_resources


def _get_project_queries(project_id: str) -> list[str]:
    """Retrieve search queries from the project's crawl tasks."""
    from sqlmodel import select
    from openlearning.database import get_session
    from openlearning.models import CrawlTask

    with get_session() as session:
        statement = (
            select(CrawlTask.query)
            .where(CrawlTask.project_id == project_id)
            .where(CrawlTask.status == "done")
            .distinct()
        )
        return list(session.exec(statement).all())


async def apply_updates(project_id: str, since_days: int = 7) -> dict:
    """Full update cycle: incremental collect + change detect + rebuild site.

    Returns a summary dict with {new, updated, removed, site_path}.
    """
    from openlearning.database import get_update_summary

    # 1. Incremental collection (new resources)
    new_resources = await incremental_collect(project_id, since_days)

    # 2. Change detection on existing resources
    report = await check_updates(project_id)

    # 3. Rebuild site if there are changes
    site_path = None
    total_changes = report.new + report.updated + len(new_resources)
    if total_changes > 0:
        site_path = await _rebuild_site(project_id)

    return {
        **report.to_dict(),
        "new_collected": len(new_resources),
        "site_path": site_path,
    }


async def _rebuild_site(project_id: str) -> str | None:
    """Rebuild the static site for a project."""
    try:
        from openlearning.agents.builder import _build_site_from_saved
        # If builder exposes a standalone rebuild function, use it
        logger.info("重建站点...")
        # Fallback: re-run the full builder
        from openlearning.skills.render import build_learning_system
        # Load saved data
        import json
        from pathlib import Path
        from openlearning.config import get_config

        output_dir = Path(get_config().output_dir)
        kg_path = output_dir / "data" / "knowledge-graph.json"
        lp_path = output_dir / "data" / "learning-path.json"

        if kg_path.exists() and lp_path.exists():
            knowledge_graph = json.loads(kg_path.read_text(encoding="utf-8"))
            learning_path = json.loads(lp_path.read_text(encoding="utf-8"))

            result = await build_learning_system.ainvoke({
                "knowledge_graph": knowledge_graph,
                "learning_path": learning_path,
                "resource_mapping": {},
            })
            logger.info("站点重建完成: %s", result.get("path", ""))
            return result.get("path", "")
    except Exception as e:
        logger.error("站点重建失败: %s", e)
    return None
