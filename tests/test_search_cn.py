"""Tests for Chinese search sources — Bilibili & Zhihu."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── Bilibili Search ─────────────────────────────────────────


class TestBilibiliSearch:
    @pytest.mark.asyncio
    async def test_basic_search(self):
        from openlearning.skills.search import bilibili_search

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "result": [
                    {
                        "bvid": "BV1xx411c7mD",
                        "title": "Rust 入门教程 <em>第1集</em>",
                        "description": "Rust 编程语言入门教程",
                        "author": "TechChannel",
                        "play": 50000,
                        "duration": "15:30",
                        "pubdate": 1700000000,
                    },
                    {
                        "bvid": "BV2yy411c7mE",
                        "title": "Rust 所有权详解",
                        "description": "深入理解 Rust 的所有权机制",
                        "author": "CodeMaster",
                        "play": 30000,
                        "duration": "20:00",
                        "pubdate": 1700100000,
                    },
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                get=AsyncMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock()

            results = await bilibili_search.ainvoke({"query": "Rust 入门", "max_results": 10})

        assert len(results) == 2
        assert results[0]["source"] == "bilibili"
        assert "BV1xx411c7mD" in results[0]["url"]
        assert "Rust" in results[0]["title"]
        assert results[0]["author"] == "TechChannel"
        assert results[0]["play_count"] == 50000

    @pytest.mark.asyncio
    async def test_html_stripped(self):
        from openlearning.skills.search import bilibili_search

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "result": [{
                    "bvid": "BV1test",
                    "title": "<em>Rust</em> 教程",
                    "description": "<b>最好</b>的教程",
                    "author": "Test",
                    "play": 100,
                    "duration": "10:00",
                    "pubdate": 1700000000,
                }]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                get=AsyncMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock()

            results = await bilibili_search.ainvoke({"query": "test"})

        assert "<em>" not in results[0]["title"]
        assert "<b>" not in results[0]["snippet"]


# ── Zhihu Search ────────────────────────────────────────────


class TestZhihuSearch:
    @pytest.mark.asyncio
    async def test_basic_search(self):
        from openlearning.skills.search import zhihu_search

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "type": "answer",
                    "object": {
                        "id": "12345",
                        "question": {"id": "67890", "title": "如何学习 Rust？"},
                        "content": "<p>Rust 是一门系统编程语言</p>",
                        "excerpt": "Rust 是一门系统编程语言，注重安全性和性能",
                        "author": {"name": "Rust专家"},
                        "voteup_count": 500,
                    },
                },
                {
                    "type": "article",
                    "object": {
                        "id": "11111",
                        "title": "Rust 入门指南",
                        "content": "<p>本文介绍 Rust 基础</p>",
                        "excerpt": "本文介绍 Rust 的基础知识",
                        "author": {"name": "编程达人"},
                        "voteup_count": 200,
                    },
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as mock_client:
            mock_ctx = MagicMock()
            mock_ctx.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock()

            results = await zhihu_search.ainvoke({"query": "学习 Rust", "max_results": 10})

        assert len(results) == 2
        assert results[0]["source"] == "zhihu"
        assert "如何学习 Rust" in results[0]["title"]
        assert results[0]["voteup_count"] == 500
        assert "zhihu.com/question/67890/answer/12345" in results[0]["url"]
        assert "zhuanlan.zhihu.com/p/11111" in results[1]["url"]

    @pytest.mark.asyncio
    async def test_html_stripped(self):
        from openlearning.skills.search import zhihu_search

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{
                "type": "answer",
                "object": {
                    "id": "1",
                    "question": {"id": "2", "title": "<b>测试</b>标题"},
                    "content": "",
                    "excerpt": "<p>摘<b>要</b>内容</p>",
                    "author": {"name": "Test"},
                    "voteup_count": 10,
                },
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as mock_client:
            mock_ctx = MagicMock()
            mock_ctx.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock()

            results = await zhihu_search.ainvoke({"query": "test"})

        assert "<b>" not in results[0]["title"]
        assert "<p>" not in results[0]["snippet"]


# ── strip_html helper ───────────────────────────────────────


class TestStripHtml:
    def test_strip_tags(self):
        from openlearning.skills.search import _strip_html

        assert _strip_html("<p>hello</p>") == "hello"
        assert _strip_html("<em>Rust</em> 教程") == "Rust 教程"
        assert _strip_html("no tags") == "no tags"
        assert _strip_html("") == ""
