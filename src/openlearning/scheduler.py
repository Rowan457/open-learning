"""Scheduler — periodic update task dispatch.

Lightweight asyncio-based scheduler that periodically checks for resource
changes and optionally rebuilds the site. Reads interval from openlearning.yaml.

Usage:
    from openlearning.scheduler import start_scheduler
    await start_scheduler("project_id")  # runs until cancelled
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from openlearning.log import get_logger

logger = get_logger("Scheduler")

INTERVAL_MAP = {
    "daily": 86400,
    "weekly": 604800,
    "monthly": 2592000,
}


def get_interval_seconds(interval: str) -> int:
    """Convert an interval name to seconds."""
    return INTERVAL_MAP.get(interval, INTERVAL_MAP["weekly"])


async def start_scheduler(
    project_id: str,
    interval: str | None = None,
    auto_regenerate: bool | None = None,
) -> None:
    """Run periodic update checks for a project.

    Args:
        project_id: The project to monitor.
        interval: Override check interval (default from config).
        auto_regenerate: Override auto-regenerate (default from config).

    This runs indefinitely until cancelled (e.g. via KeyboardInterrupt).
    """
    from openlearning.config import get_config
    from openlearning.agents.updater import check_updates, apply_updates

    config = get_config()
    update_cfg = config.updates

    if interval is None:
        interval = getattr(update_cfg, "check_interval", "weekly")
    if auto_regenerate is None:
        auto_regenerate = getattr(update_cfg, "auto_regenerate", True)

    seconds = get_interval_seconds(interval)
    logger.info(
        "调度器启动: 项目=%s, 间隔=%s (%ss), 自动重建=%s",
        project_id, interval, seconds, auto_regenerate,
    )

    while True:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        logger.info("[%s] 开始定时检查...", now)

        try:
            if auto_regenerate:
                result = await apply_updates(project_id)
                logger.info(
                    "更新完成: 新增=%s 更新=%s 失效=%s",
                    result.get("new", 0),
                    result.get("updated", 0),
                    result.get("removed", 0),
                )
                if result.get("site_path"):
                    logger.info("站点已重建: %s", result["site_path"])
            else:
                report = await check_updates(project_id)
                logger.info("变更检测: %s", report.summary())

        except Exception as e:
            logger.error("定时检查失败: %s", e)

        logger.info("下次检查: %s 后", interval)
        await asyncio.sleep(seconds)


async def run_once(project_id: str, auto_regenerate: bool = True) -> dict:
    """Run a single update check (non-recurring).

    Returns the update result dict.
    """
    from openlearning.agents.updater import check_updates, apply_updates

    if auto_regenerate:
        return await apply_updates(project_id)
    else:
        report = await check_updates(project_id)
        return report.to_dict()
