"""Tests for Search Skill — date filtering (since_days)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from openlearning.skills.search import (
    _duckduckgo_search,
    _serpapi_search,
    _tavily_search,
    _since_iso,
    _since_yyyymmdd,
)


class TestSerpApiSinceDays:
    @pytest.mark.asyncio
    async def test_since_days_adds_tbs_week(self):
        """since_days=7 should add tbs=qdr:w to SerpAPI params."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"organic_results": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_resp)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await _serpapi_search("test", 10, "fake_key", since_days=7)

            call_kwargs = instance.get.call_args
            params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
            assert params.get("tbs") == "qdr:w"

    @pytest.mark.asyncio
    async def test_no_since_days_no_tbs(self):
        """No since_days → no tbs param."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"organic_results": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_resp)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await _serpapi_search("test", 10, "fake_key", since_days=None)

            call_kwargs = instance.get.call_args
            params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
            assert "tbs" not in params


class TestTavilySinceDays:
    @pytest.mark.asyncio
    async def test_since_days_adds_days_param(self):
        """since_days=14 should add days=14 to Tavily payload."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post = AsyncMock(return_value=mock_resp)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await _tavily_search("test", 10, "fake_key", since_days=14)

            call_kwargs = instance.post.call_args
            payload = call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {}))
            assert payload.get("days") == 14

    @pytest.mark.asyncio
    async def test_no_since_days_no_days_key(self):
        """No since_days → no days key in payload."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post = AsyncMock(return_value=mock_resp)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await _tavily_search("test", 10, "fake_key", since_days=None)

            call_kwargs = instance.post.call_args
            payload = call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {}))
            assert "days" not in payload


class TestDuckDuckGoSinceDays:
    @pytest.mark.asyncio
    async def test_since_days_adds_df_week(self):
        """since_days=7 should add df=w to DuckDuckGo params."""
        mock_resp = MagicMock()
        mock_resp.text = "<html></html>"
        mock_resp.raise_for_status = MagicMock()

        with patch("openlearning.skills.search.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_resp)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await _duckduckgo_search("test", 10, since_days=7)

            call_kwargs = instance.get.call_args
            params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
            assert params.get("df") == "w"


class TestDateHelpers:
    def test_since_iso_format(self):
        assert len(_since_iso(0)) == 10
        assert _since_iso(0)[4] == "-"

    def test_since_yyyymmdd_format(self):
        assert len(_since_yyyymmdd(0)) == 8
        assert _since_yyyymmdd(0).isdigit()

    def test_since_yyyymmdd_30_days_ago(self):
        from datetime import datetime, timedelta, timezone
        expected = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y%m%d")
        assert _since_yyyymmdd(30) == expected
