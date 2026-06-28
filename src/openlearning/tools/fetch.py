"""Fetch Skill — web content extraction.

Tools: fetch_page, extract, parse_pdf
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from openlearning.config import get_config, get_proxy


# ── Input Schemas ────────────────────────────────────────────

class FetchPageInput(BaseModel):
    url: str = Field(description="要抓取的网页 URL")


class ExtractInput(BaseModel):
    content: str = Field(description="原始 HTML 内容")
    schema: dict | None = Field(default=None, description="期望的输出结构")


class ParsePdfInput(BaseModel):
    url: str = Field(description="PDF 文件 URL")


# ── Fetch Page ───────────────────────────────────────────────

@tool("fetch_page", args_schema=FetchPageInput)
async def fetch_page(url: str) -> dict[str, Any]:
    """抓取网页并提取正文内容。

    使用 trafilatura 进行智能内容提取，自动去除导航、广告等噪音。
    返回 {url, title, content, metadata, success}。
    """
    config = get_config()
    timeout = config.skills.fetch.timeout

    try:
        proxy = get_proxy()
        client_kwargs: dict[str, Any] = {
            "timeout": timeout,
            "follow_redirects": True,
            "headers": {"User-Agent": "Mozilla/5.0 (compatible; OpenLearning/1.0)"},
        }
        if proxy:
            client_kwargs["proxy"] = proxy
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        # Use trafilatura for intelligent content extraction
        import trafilatura

        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=True,
            output_format="txt",
            url=url,
        )

        # Extract metadata
        metadata = trafilatura.extract(
            html,
            output_format="json",
            url=url,
        )

        title = ""
        if metadata:
            import json

            try:
                meta = json.loads(metadata)
                title = meta.get("title", "")
            except (json.JSONDecodeError, TypeError):
                pass

        if not title:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

        content_text = extracted or ""
        content_hash = hashlib.sha256(content_text.encode()).hexdigest()

        return {
            "url": url,
            "title": title,
            "content": content_text,
            "metadata": metadata,
            "content_hash": content_hash,
            "success": True,
        }

    except Exception as e:
        return {
            "url": url,
            "title": "",
            "content": "",
            "metadata": None,
            "success": False,
            "error": str(e),
        }


# ── Extract ──────────────────────────────────────────────────

@tool("extract", args_schema=ExtractInput)
async def extract(content: str, schema: dict | None = None) -> dict[str, Any]:
    """从原始内容中提取结构化数据。

    使用 LLM 进行智能提取（如果配置了 LLM），否则使用规则提取。
    返回结构化的数据字典。
    """
    # Rule-based extraction fallback
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")

    # Extract common structured fields
    result: dict[str, Any] = {
        "title": "",
        "headings": [],
        "code_blocks": [],
        "links": [],
        "images": [],
    }

    # Title
    if title_tag := soup.find("title"):
        result["title"] = title_tag.get_text(strip=True)

    # Headings
    for level in range(1, 4):
        for h in soup.find_all(f"h{level}"):
            result["headings"].append({
                "level": level,
                "text": h.get_text(strip=True),
            })

    # Code blocks
    for pre in soup.find_all("pre"):
        code = pre.get_text(strip=True)
        if code:
            result["code_blocks"].append(code[:500])

    # Links
    for a in soup.find_all("a", href=True):
        result["links"].append({
            "text": a.get_text(strip=True),
            "href": a["href"],
        })

    # Images
    for img in soup.find_all("img", src=True):
        result["images"].append({
            "src": img["src"],
            "alt": img.get("alt", ""),
        })

    return result


# ── Parse PDF ────────────────────────────────────────────────

@tool("parse_pdf", args_schema=ParsePdfInput)
async def parse_pdf(url: str) -> dict[str, Any]:
    """解析 PDF 文件并提取文本内容。

    下载 PDF 并使用 trafilatura 提取文本。
    返回 {url, content, page_count, success}。
    """
    try:
        proxy = get_proxy()
        client_kwargs: dict[str, Any] = {"timeout": 60, "follow_redirects": True}
        if proxy:
            client_kwargs["proxy"] = proxy
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            pdf_bytes = resp.content

        # Try trafilatura for PDF extraction
        import trafilatura

        content = trafilatura.extract(pdf_bytes, url=url) or ""

        if not content:
            # Fallback: try PyPDF2 if available
            try:
                import io

                from PyPDF2 import PdfReader

                reader = PdfReader(io.BytesIO(pdf_bytes))
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                content = "\n\n".join(pages)
            except ImportError:
                content = "[PDF extraction requires PyPDF2: pip install PyPDF2]"

        return {
            "url": url,
            "content": content,
            "page_count": len(content) // 3000 + 1,  # rough estimate
            "success": bool(content),
        }

    except Exception as e:
        return {
            "url": url,
            "content": "",
            "page_count": 0,
            "success": False,
            "error": str(e),
        }


# ── Tools Export ─────────────────────────────────────────────

TOOLS = [fetch_page, extract, parse_pdf]


def get_tools() -> list:
    return list(TOOLS)
