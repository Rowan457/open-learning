"""Search Skill — multi-source web search.

Tools: web_search, arxiv_search, youtube_search, github_search
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from openlearning.config import get_config


# ── Input Schemas ────────────────────────────────────────────

class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=20, description="最大结果数")
    since_days: int | None = Field(default=None, description="只搜索最近 N 天的内容")


class ArxivInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=10, description="最大结果数")
    since_days: int | None = Field(default=None, description="只搜索最近 N 天的内容")


class GitHubInput(BaseModel):
    query: str = Field(description="搜索关键词")
    language: str | None = Field(default=None, description="编程语言过滤")
    since_days: int | None = Field(default=None, description="只搜索最近 N 天的内容")


def _since_date(days: int) -> datetime:
    """Compute the UTC datetime N days ago."""
    return datetime.now(timezone.utc) - timedelta(days=days)


def _since_iso(days: int) -> str:
    """ISO date string N days ago (YYYY-MM-DD)."""
    return _since_date(days).strftime("%Y-%m-%d")


def _since_yyyymmdd(days: int) -> str:
    """Compact date string N days ago (YYYYMMDD) for arXiv."""
    return _since_date(days).strftime("%Y%m%d")


# ── Google Search ────────────────────────────────────────────

@tool("web_search", args_schema=SearchInput)
async def web_search(
    query: str, max_results: int = 20, since_days: int | None = None
) -> list[dict[str, Any]]:
    """搜索网页资源。

    优先级: SerpAPI → Tavily → DuckDuckGo
    返回 [{url, title, snippet, source}] 列表。
    """
    config = get_config()
    providers = config.skills.search.providers

    # Try SerpAPI first
    if google_cfg := providers.get("google"):
        if google_cfg.api_key:
            return await _serpapi_search(query, max_results, google_cfg.api_key, since_days)

    # Try Tavily
    if tavily_cfg := providers.get("tavily"):
        if tavily_cfg.api_key:
            return await _tavily_search(query, max_results, tavily_cfg.api_key, since_days)

    # Fallback to DuckDuckGo (free, no API key needed)
    return await _duckduckgo_search(query, max_results, since_days)


async def _tavily_search(
    query: str, max_results: int, api_key: str, since_days: int | None = None
) -> list[dict]:
    """Search via Tavily API (AI-optimized search)."""
    payload = {
        "query": query,
        "api_key": api_key,
        "max_results": min(max_results, 20),
        "include_answer": False,
        "include_raw_content": False,
    }
    if since_days is not None:
        payload["days"] = since_days

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("results", [])[:max_results]:
        results.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "snippet": item.get("content", "")[:300],
            "source": "tavily",
        })
    return results


async def _serpapi_search(
    query: str, max_results: int, api_key: str, since_days: int | None = None
) -> list[dict]:
    """Search via SerpAPI."""
    params = {
        "q": query,
        "num": max_results,
        "api_key": api_key,
        "engine": "google",
    }
    if since_days is not None:
        if since_days <= 1:
            params["tbs"] = "qdr:d"
        elif since_days <= 7:
            params["tbs"] = "qdr:w"
        elif since_days <= 30:
            params["tbs"] = "qdr:m"
        elif since_days <= 365:
            params["tbs"] = "qdr:y"
        else:
            params["tbs"] = f"cdr:1,cd_min:{_since_iso(since_days)}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic_results", [])[:max_results]:
        results.append({
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "source": "google",
        })
    return results


async def _duckduckgo_search(
    query: str, max_results: int, since_days: int | None = None
) -> list[dict]:
    """Fallback search using DuckDuckGo HTML (no API key)."""
    params: dict[str, Any] = {"q": query}
    if since_days is not None:
        if since_days <= 1:
            params["df"] = "d"
        elif since_days <= 7:
            params["df"] = "w"
        elif since_days <= 30:
            params["df"] = "m"
        else:
            params["df"] = "y"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://html.duckduckgo.com/html/",
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for link in soup.select(".result__a")[:max_results]:
        url = link.get("href", "")
        title = link.get_text(strip=True)
        snippet_el = link.find_next(".result__snippet")
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        if url.startswith("http"):
            results.append({
                "url": url,
                "title": title,
                "snippet": snippet,
                "source": "duckduckgo",
            })
    return results


# ── arXiv Search ─────────────────────────────────────────────

@tool("arxiv_search", args_schema=ArxivInput)
async def arxiv_search(
    query: str, max_results: int = 10, since_days: int | None = None
) -> list[dict[str, Any]]:
    """搜索 arXiv 学术论文。

    使用 arXiv API (免费，无需 API key)。
    返回 [{url, title, snippet, authors, published, source}] 列表。
    """
    import xml.etree.ElementTree as ET

    search_query = f"all:{query}"
    if since_days is not None:
        date_str = _since_yyyymmdd(since_days)
        search_query += f" AND submittedDate:[{date_str} TO 99999999]"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": search_query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
        )
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    results = []
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")[:300]
        url = ""
        for link in entry.findall("atom:link", ns):
            if link.get("type") == "text/html":
                url = link.get("href", "")
                break
        if not url:
            url = entry.findtext("atom:id", "", ns)

        authors = [
            a.findtext("atom:name", "", ns)
            for a in entry.findall("atom:author", ns)
        ]
        published = entry.findtext("atom:published", "", ns)[:10]

        results.append({
            "url": url,
            "title": title,
            "snippet": summary,
            "authors": authors,
            "published": published,
            "source": "arxiv",
        })
    return results


# ── YouTube Search ───────────────────────────────────────────

@tool("youtube_search", args_schema=SearchInput)
async def youtube_search(
    query: str, max_results: int = 10, since_days: int | None = None
) -> list[dict[str, Any]]:
    """搜索 YouTube 视频教程。

    使用 YouTube Data API v3。
    返回 [{url, title, snippet, channel, published, source}] 列表。
    """
    config = get_config()
    providers = config.skills.search.providers
    yt_cfg = providers.get("youtube")

    if not yt_cfg or not yt_cfg.api_key:
        # Fallback: search via DuckDuckGo with site: filter
        return await _duckduckgo_search(f"site:youtube.com {query}", max_results, since_days)

    params: dict[str, Any] = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": yt_cfg.api_key,
        "relevanceLanguage": "zh",
    }
    if since_days is not None:
        params["publishedAfter"] = _since_date(since_days).strftime("%Y-%m-%dT%H:%M:%SZ")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("items", []):
        vid = item["id"]["videoId"]
        snippet = item["snippet"]
        results.append({
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": snippet.get("title", ""),
            "snippet": snippet.get("description", "")[:300],
            "channel": snippet.get("channelTitle", ""),
            "published": snippet.get("publishedAt", "")[:10],
            "source": "youtube",
        })
    return results


# ── GitHub Search ────────────────────────────────────────────

@tool("github_search", args_schema=GitHubInput)
async def github_search(
    query: str, language: str | None = None, since_days: int | None = None
) -> list[dict[str, Any]]:
    """搜索 GitHub 代码仓库。

    使用 GitHub REST API (可选 token 提升限额)。
    返回 [{url, title, snippet, stars, language, source}] 列表。
    """
    config = get_config()
    providers = config.skills.search.providers
    gh_cfg = providers.get("github")

    headers = {"Accept": "application/vnd.github.v3+json"}
    if gh_cfg and gh_cfg.api_key:
        headers["Authorization"] = f"token {gh_cfg.api_key}"

    q = query
    if language:
        q += f" language:{language}"
    if since_days is not None:
        q += f" created:>={_since_iso(since_days)}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://api.github.com/search/repositories",
            params={"q": q, "sort": "stars", "per_page": 20},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("items", [])[:20]:
        results.append({
            "url": item.get("html_url", ""),
            "title": item.get("full_name", ""),
            "snippet": (item.get("description") or "")[:300],
            "stars": item.get("stargazers_count", 0),
            "language": item.get("language", ""),
            "source": "github",
        })
    return results


# ── Bilibili Search ──────────────────────────────────────────

class BilibiliInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=20, description="最大结果数")
    since_days: int | None = Field(default=None, description="只搜索最近 N 天的内容")


@tool("bilibili_search", args_schema=BilibiliInput)
async def bilibili_search(
    query: str, max_results: int = 20, since_days: int | None = None
) -> list[dict[str, Any]]:
    """搜索 Bilibili 视频教程。

    使用 Bilibili 搜索 API (免费，无需 API key)。
    返回 [{url, title, snippet, author, play_count, duration, published, source}] 列表。
    """
    params: dict[str, Any] = {
        "keyword": query,
        "search_type": "video",
        "order": "totalrank",  # 综合排序
        "page": 1,
        "page_size": min(max_results, 50),
    }

    # Bilibili 搜索时间过滤: 0=不限, 1=1天, 7=7天, 30=30天, 182=半年
    if since_days is not None:
        if since_days <= 1:
            params["duration"] = 0
            params["tids_1"] = 0
            # 使用 pubtime_begin/pubtime_end 做时间过滤
            params["pubtime_begin"] = _since_date(since_days).strftime("%Y-%m-%d")
            params["pubtime_end"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        elif since_days <= 7:
            params["pubtime_begin"] = _since_date(since_days).strftime("%Y-%m-%d")
            params["pubtime_end"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        elif since_days <= 30:
            params["pubtime_begin"] = _since_date(since_days).strftime("%Y-%m-%d")
            params["pubtime_end"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        else:
            params["pubtime_begin"] = _since_date(since_days).strftime("%Y-%m-%d")
            params["pubtime_end"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://search.bilibili.com/",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("data", {}).get("result", [])[:max_results]:
        # Bilibili 返回的 duration 格式: "12:34" 或秒数
        duration = item.get("duration", "")

        # 发布时间 (时间戳)
        pubdate = item.get("pubdate", 0)
        published = ""
        if pubdate:
            published = datetime.fromtimestamp(pubdate, tz=timezone.utc).strftime("%Y-%m-%d")

        # 播放量
        play = item.get("play", 0)
        if isinstance(play, str):
            play = int(play.replace(",", "")) if play.replace(",", "").isdigit() else 0

        results.append({
            "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
            "title": _strip_html(item.get("title", "")),
            "snippet": _strip_html(item.get("description", ""))[:300],
            "author": item.get("author", ""),
            "play_count": play,
            "duration": duration,
            "published": published,
            "source": "bilibili",
        })
    return results


# ── Zhihu Search ─────────────────────────────────────────────

class ZhihuInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=20, description="最大结果数")
    search_type: str = Field(default="general", description="搜索类型: general/answer/article")


@tool("zhihu_search", args_schema=ZhihuInput)
async def zhihu_search(
    query: str, max_results: int = 20, search_type: str = "general"
) -> list[dict[str, Any]]:
    """搜索知乎问答和专栏文章。

    使用知乎搜索 API (免费，无需 API key)。
    返回 [{url, title, snippet, author, voteup_count, source}] 列表。
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.zhihu.com/search",
    }

    results: list[dict] = []

    # Use Zhihu's search API endpoint
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # General search (mix of answers and articles)
        params = {
            "q": query,
            "type": "content",
            "offset": 0,
            "limit": min(max_results, 20),
        }

        try:
            resp = await client.get(
                "https://www.zhihu.com/api/v4/search_v3",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("data", [])[:max_results]:
                obj = item.get("object", {})
                item_type = item.get("type", "")

                if item_type in ("answer", "article"):
                    title = obj.get("question", {}).get("title", "") or obj.get("title", "")
                    content = obj.get("excerpt", "") or obj.get("content", "")
                    author = obj.get("author", {}).get("name", "")

                    # URL construction
                    if item_type == "answer":
                        q_id = obj.get("question", {}).get("id", "")
                        a_id = obj.get("id", "")
                        url = f"https://www.zhihu.com/question/{q_id}/answer/{a_id}"
                    else:
                        url = f"https://zhuanlan.zhihu.com/p/{obj.get('id', '')}"

                    results.append({
                        "url": url,
                        "title": _strip_html(title),
                        "snippet": _strip_html(content)[:300],
                        "author": author,
                        "voteup_count": obj.get("voteup_count", 0),
                        "source": "zhihu",
                    })
        except httpx.HTTPStatusError:
            # Fallback: use DuckDuckGo with site:zhihu.com filter
            return await _duckduckgo_search(f"site:zhihu.com {query}", max_results)

    return results


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    return clean.strip()


# ── Tools Export ─────────────────────────────────────────────

TOOLS = [web_search, arxiv_search, youtube_search, github_search, bilibili_search, zhihu_search]


def get_tools() -> list:
    return list(TOOLS)
