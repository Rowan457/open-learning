"""Example plugin: RSS feed collector.

Demonstrates how to create a custom collector plugin.
Copy this file and modify to create your own plugin.

Usage:
    1. Copy this file to plugins/my_plugin.py
    2. Implement your search logic
    3. Run: openlearning plugin list
"""

from __future__ import annotations

from typing import Any

import httpx

from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult


class RssCollector(BaseCollector):
    """Example RSS feed collector plugin.

    Searches RSS feeds for articles matching a query.
    """

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="example-rss",
            version="0.1.0",
            description="从 RSS 订阅源搜索文章 (示例插件)",
            author="OpenLearning",
            source_type="rss",
            requires_api_key=False,
        )

    async def search(
        self,
        query: str,
        max_results: int = 20,
        feed_url: str = "",
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Search RSS feed for matching items.

        Args:
            query: search keywords
            max_results: max results to return
            feed_url: RSS feed URL (required)

        Returns:
            List of SearchResult objects.
        """
        if not feed_url:
            # Use a default tech blog feed for demo
            feed_url = "https://hnrss.org/newest"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    feed_url,
                    params={"q": query},
                    headers={"User-Agent": "OpenLearning/0.1"},
                )
                resp.raise_for_status()

            # Parse RSS XML (simple approach)
            import xml.etree.ElementTree as ET

            root = ET.fromstring(resp.text)
            items = root.findall(".//item")

            results = []
            query_lower = query.lower()

            for item in items[:max_results]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                description = item.findtext("description", "").strip()
                pub_date = item.findtext("pubDate", "").strip()

                # Simple relevance filter
                text = f"{title} {description}".lower()
                if query_lower not in text:
                    continue

                results.append(SearchResult(
                    url=link,
                    title=title,
                    snippet=description[:300],
                    source="rss",
                    published=pub_date,
                ))

            return results

        except Exception as e:
            return [SearchResult(
                url="",
                title=f"RSS 搜索失败: {e}",
                snippet="",
                source="rss",
            )]

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if "feed_url" in config and not config["feed_url"].startswith("http"):
            errors.append("feed_url 必须是有效的 HTTP URL")
        return errors
