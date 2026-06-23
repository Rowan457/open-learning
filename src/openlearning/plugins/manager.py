"""Plugin Manager — discovery, loading, and lifecycle management.

Supports:
- Directory-based plugin discovery (plugins/ directory)
- YAML configuration (plugins.yaml)
- Hot-reload on config change
- Enable/disable individual plugins
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import yaml

from openlearning.log import get_logger
from openlearning.plugins.base import BaseCollector, PluginMeta, SearchResult

logger = get_logger("PluginManager")

# Default plugin directories
DEFAULT_PLUGIN_DIR = Path("plugins")
DEFAULT_CONFIG_FILE = Path("plugins.yaml")


class PluginManager:
    """Manages discovery, loading, and lifecycle of collector plugins.

    Usage:
        pm = PluginManager()
        pm.discover()  # scan plugin directory
        pm.load_all()  # load all enabled plugins

        # Use a plugin
        results = await pm.search("my-plugin", "query", max_results=10)
    """

    def __init__(
        self,
        plugin_dir: Path | str | None = None,
        config_file: Path | str | None = None,
    ) -> None:
        self._plugin_dir = Path(plugin_dir) if plugin_dir else DEFAULT_PLUGIN_DIR
        self._config_file = Path(config_file) if config_file else DEFAULT_CONFIG_FILE
        self._plugins: dict[str, BaseCollector] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._enabled: dict[str, bool] = {}
        self._discovered = False

    @property
    def plugin_dir(self) -> Path:
        return self._plugin_dir

    @property
    def config_file(self) -> Path:
        return self._config_file

    def discover(self) -> list[str]:
        """Scan plugin directory for Python modules with BaseCollector subclasses.

        Returns list of discovered plugin names.
        """
        discovered = []

        if not self._plugin_dir.exists():
            logger.debug("插件目录不存在: %s", self._plugin_dir)
            return discovered

        # Load config first
        self._load_config()

        # Scan for .py files and packages
        for item in sorted(self._plugin_dir.iterdir()):
            if item.name.startswith("_"):
                continue

            plugin_name = None
            module_path = None

            if item.is_file() and item.suffix == ".py":
                plugin_name = item.stem
                module_path = str(item)
            elif item.is_dir() and (item / "__init__.py").exists():
                plugin_name = item.name
                module_path = str(item / "__init__.py")

            if plugin_name and module_path:
                try:
                    self._load_plugin_module(plugin_name, module_path)
                    discovered.append(plugin_name)
                    logger.info("发现插件: %s", plugin_name)
                except Exception as e:
                    logger.warning("加载插件 %s 失败: %s", plugin_name, e)

        self._discovered = True
        return discovered

    def _load_plugin_module(self, name: str, module_path: str) -> None:
        """Load a single plugin module and register its collectors."""
        spec = importlib.util.spec_from_file_location(f"plugins.{name}", module_path)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"plugins.{name}"] = module
        spec.loader.exec_module(module)

        # Find BaseCollector subclasses
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseCollector)
                and attr is not BaseCollector
            ):
                instance = attr()
                plugin_name = instance.meta.name or name

                # Check if enabled in config
                config = self._configs.get(plugin_name, {})
                enabled = config.get("enabled", True)
                self._enabled[plugin_name] = enabled

                # Apply config to instance if it has a configure method
                if hasattr(instance, "configure") and config:
                    try:
                        instance.configure(config)
                    except Exception as e:
                        logger.warning("配置插件 %s 失败: %s", plugin_name, e)

                self._plugins[plugin_name] = instance
                logger.debug("注册插件: %s (enabled=%s)", plugin_name, enabled)

    def _load_config(self) -> None:
        """Load plugin configuration from YAML file."""
        if not self._config_file.exists():
            return

        try:
            with open(self._config_file, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            for name, plugin_config in config.get("plugins", {}).items():
                if isinstance(plugin_config, dict):
                    self._configs[name] = plugin_config
                else:
                    self._configs[name] = {"enabled": bool(plugin_config)}

            logger.debug("加载插件配置: %s", list(self._configs.keys()))
        except Exception as e:
            logger.warning("读取插件配置失败: %s", e)

    def load_all(self) -> dict[str, BaseCollector]:
        """Load all enabled plugins. Returns name→instance mapping."""
        if not self._discovered:
            self.discover()

        return {
            name: plugin
            for name, plugin in self._plugins.items()
            if self._enabled.get(name, True)
        }

    def get(self, name: str) -> BaseCollector | None:
        """Get a plugin by name."""
        if not self._discovered:
            self.discover()
        return self._plugins.get(name)

    def enable(self, name: str) -> bool:
        """Enable a plugin. Returns True if found."""
        if name in self._plugins:
            self._enabled[name] = True
            self._save_config()
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a plugin. Returns True if found."""
        if name in self._plugins:
            self._enabled[name] = False
            self._save_config()
            return True
        return False

    def _save_config(self) -> None:
        """Save current enable/disable state to config file."""
        config = {"plugins": {}}
        for name in self._plugins:
            config["plugins"][name] = {"enabled": self._enabled.get(name, True)}

        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.warning("保存插件配置失败: %s", e)

    async def search(
        self,
        plugin_name: str,
        query: str,
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Search using a specific plugin.

        Returns list of result dicts compatible with the existing pipeline.
        """
        plugin = self.get(plugin_name)
        if plugin is None:
            raise KeyError(f"Plugin '{plugin_name}' not found")

        if not self._enabled.get(plugin_name, True):
            logger.warning("插件 %s 已禁用", plugin_name)
            return []

        results = await plugin.search(query, max_results=max_results, **kwargs)
        return [r.to_dict() for r in results]

    async def search_all(
        self,
        query: str,
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Search across all enabled plugins.

        Returns combined, deduplicated results.
        """
        import asyncio

        tasks = []
        names = []
        for name, plugin in self.load_all().items():
            tasks.append(self.search(name, query, max_results=max_results, **kwargs))
            names.append(name)

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = []
        seen_urls: set[str] = set()
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.warning("插件 %s 搜索失败: %s", name, result)
                continue
            for r in result:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)

        return all_results

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all discovered plugins with their metadata."""
        if not self._discovered:
            self.discover()

        result = []
        for name, plugin in self._plugins.items():
            meta = plugin.meta
            result.append({
                "name": name,
                "version": meta.version,
                "description": meta.description,
                "author": meta.author,
                "source_type": meta.source_type,
                "requires_api_key": meta.requires_api_key,
                "enabled": self._enabled.get(name, True),
            })
        return result

    def reload(self) -> list[str]:
        """Reload all plugins from disk.

        Returns list of reloaded plugin names.
        """
        self._plugins.clear()
        self._configs.clear()
        self._enabled.clear()
        self._discovered = False
        return self.discover()
