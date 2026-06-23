"""示例: 豆瓣电影学习资源采集器。

搜索豆瓣电影中的纪录片/教程类视频。
"""

from __future__ import annotations

from typing import Any

import httpx

from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult


class DoubanMovieCollector(BaseCollector):
    """从豆瓣搜索纪录片/教育类视频。"""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="douban-movies",
            version="0.1.0",
            description="搜索豆瓣纪录片和教育视频",
            author="User",
            source_type="douban",
            requires_api_key=False,
        )

    async def search(
        self,
        query: str,
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """搜索豆瓣电影。

        使用豆瓣搜索 API (无需 key，但有频率限制)。
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://movie.douban.com/",
        }

        results = []
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    "https://movie.douban.com/j/subject_suggest",
                    params={"q": query, "type": "movie"},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data[:max_results]:
                    title = item.get("title", "")
                    year = item.get("year", "")
                    sub_url = item.get("url", "")
                    img = item.get("img", "")

                    results.append(SearchResult(
                        url=sub_url,
                        title=f"{title} ({year})" if year else title,
                        snippet=f"豆瓣电影: {title}",
                        source="douban",
                        extra={
                            "year": year,
                            "poster": img,
                            "resource_type": "video",
                        },
                    ))

            except Exception:
                pass

        return results
