"""Tests for Plugin System — BaseCollector, PluginManager."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult


# ── Fixtures ────────────────────────────────────────────────


class MockCollector(BaseCollector):
    """Test collector implementation."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="test-collector",
            version="1.0.0",
            description="Test collector",
            source_type="test",
        )

    async def search(self, query: str, max_results: int = 20, **kwargs):
        return [
            SearchResult(
                url=f"https://example.com/{query}",
                title=f"Result for {query}",
                snippet="A test result",
                source="test",
            ),
        ]


# ── SearchResult ────────────────────────────────────────────


class TestSearchResult:
    def test_to_dict(self):
        r = SearchResult(
            url="https://example.com",
            title="Test",
            snippet="Snippet",
            source="test",
            author="Author",
        )
        d = r.to_dict()
        assert d["url"] == "https://example.com"
        assert d["title"] == "Test"
        assert d["source"] == "test"
        assert d["author"] == "Author"

    def test_extra_fields(self):
        r = SearchResult(
            url="https://example.com",
            title="Test",
            extra={"play_count": 1000, "duration": "10:00"},
        )
        d = r.to_dict()
        assert d["play_count"] == 1000
        assert d["duration"] == "10:00"


# ── BaseCollector ───────────────────────────────────────────


class TestBaseCollector:
    def test_meta(self):
        c = MockCollector()
        assert c.meta.name == "test-collector"
        assert c.meta.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_search(self):
        c = MockCollector()
        results = await c.search("test query")
        assert len(results) == 1
        assert results[0].title == "Result for test query"

    def test_repr(self):
        c = MockCollector()
        assert "MockCollector" in repr(c)
        assert "test-collector" in repr(c)

    def test_validate_config_empty(self):
        c = MockCollector()
        errors = c.validate_config({})
        assert errors == []


# ── PluginManager ───────────────────────────────────────────


class TestPluginManager:
    def test_init_defaults(self):
        from openlearning.plugins.manager import PluginManager

        pm = PluginManager()
        assert pm.plugin_dir == Path("plugins")
        assert pm.config_file == Path("plugins.yaml")

    def test_discover_empty_dir(self):
        from openlearning.plugins.manager import PluginManager

        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PluginManager(plugin_dir=tmpdir)
            discovered = pm.discover()
            assert discovered == []

    def test_discover_with_plugin(self):
        from openlearning.plugins.manager import PluginManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test plugin file
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text('''
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

class TestPlugin(BaseCollector):
    @property
    def meta(self):
        return PluginMeta(name="test-plugin", description="Test")

    async def search(self, query, max_results=20, **kwargs):
        return [SearchResult(url="https://test.com", title="Test", source="test")]
''', encoding="utf-8")

            pm = PluginManager(plugin_dir=tmpdir)
            discovered = pm.discover()
            assert "test_plugin" in discovered

    def test_enable_disable(self):
        from openlearning.plugins.manager import PluginManager

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text('''
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

class TestPlugin(BaseCollector):
    @property
    def meta(self):
        return PluginMeta(name="test-plugin", description="Test")

    async def search(self, query, max_results=20, **kwargs):
        return []
''', encoding="utf-8")

            pm = PluginManager(plugin_dir=tmpdir)
            pm.discover()

            assert pm.disable("test-plugin") is True
            assert pm.get("test-plugin") is not None  # still exists

            assert pm.enable("test-plugin") is True
            assert pm.disable("nonexistent") is False

    def test_list_plugins(self):
        from openlearning.plugins.manager import PluginManager

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text('''
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

class TestPlugin(BaseCollector):
    @property
    def meta(self):
        return PluginMeta(name="test-plugin", description="Test plugin", version="1.0")

    async def search(self, query, max_results=20, **kwargs):
        return []
''', encoding="utf-8")

            pm = PluginManager(plugin_dir=tmpdir)
            pm.discover()

            plugins = pm.list_plugins()
            assert len(plugins) == 1
            assert plugins[0]["name"] == "test-plugin"
            assert plugins[0]["description"] == "Test plugin"

    @pytest.mark.asyncio
    async def test_search_via_manager(self):
        from openlearning.plugins.manager import PluginManager

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text('''
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

class TestPlugin(BaseCollector):
    @property
    def meta(self):
        return PluginMeta(name="test-plugin", description="Test")

    async def search(self, query, max_results=20, **kwargs):
        return [SearchResult(url="https://test.com/q=" + query, title="Found: " + query, source="test")]
''', encoding="utf-8")

            pm = PluginManager(plugin_dir=tmpdir)
            pm.discover()

            results = await pm.search("test-plugin", "hello")
            assert len(results) == 1
            assert results[0]["title"] == "Found: hello"

    @pytest.mark.asyncio
    async def test_search_disabled_plugin(self):
        from openlearning.plugins.manager import PluginManager

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "test_plugin.py"
            plugin_file.write_text('''
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

class TestPlugin(BaseCollector):
    @property
    def meta(self):
        return PluginMeta(name="test-plugin", description="Test")

    async def search(self, query, max_results=20, **kwargs):
        return [SearchResult(url="https://test.com", title="Test", source="test")]
''', encoding="utf-8")

            pm = PluginManager(plugin_dir=tmpdir)
            pm.discover()
            pm.disable("test-plugin")

            results = await pm.search("test-plugin", "hello")
            assert results == []

    def test_reload(self):
        from openlearning.plugins.manager import PluginManager

        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PluginManager(plugin_dir=tmpdir)
            assert pm.discover() == []

            # Add a plugin file
            plugin_file = Path(tmpdir) / "new_plugin.py"
            plugin_file.write_text('''
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

class NewPlugin(BaseCollector):
    @property
    def meta(self):
        return PluginMeta(name="new-plugin", description="New")

    async def search(self, query, max_results=20, **kwargs):
        return []
''', encoding="utf-8")

            discovered = pm.reload()
            assert "new_plugin" in discovered


# ── Plugin Config ───────────────────────────────────────────


class TestPluginConfig:
    def test_load_yaml_config(self):
        from openlearning.plugins.manager import PluginManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config file
            config_file = Path(tmpdir) / "plugins.yaml"
            config_file.write_text('''
plugins:
  my-plugin:
    enabled: true
    api_key: "test-key"
''', encoding="utf-8")

            # Create plugin
            plugin_file = Path(tmpdir) / "my_plugin.py"
            plugin_file.write_text('''
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

class MyPlugin(BaseCollector):
    @property
    def meta(self):
        return PluginMeta(name="my-plugin", description="My plugin")

    async def search(self, query, max_results=20, **kwargs):
        return []
''', encoding="utf-8")

            pm = PluginManager(plugin_dir=tmpdir, config_file=config_file)
            pm.discover()

            plugins = pm.list_plugins()
            assert len(plugins) == 1
            assert plugins[0]["enabled"] is True
