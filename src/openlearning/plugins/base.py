"""Plugin base classes — abstract interfaces for user-defined collectors.

Users subclass BaseCollector to create custom data source plugins.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginMeta:
    """Metadata for a plugin."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    source_type: str = ""  # e.g. "bilibili", "zhihu", "custom"
    requires_api_key: bool = False


@dataclass
class SearchResult:
    """Standardized search result from any plugin."""

    url: str
    title: str
    snippet: str = ""
    source: str = ""
    author: str = ""
    published: str = ""
    score: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for interop with existing pipeline."""
        d = {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet[:300],
            "source": self.source or self.__class__.__name__,
            "author": self.author,
            "published": self.published,
        }
        if self.extra:
            d.update(self.extra)
        return d


class BaseCollector(abc.ABC):
    """Abstract base class for custom data source collectors.

    Subclass this to create a new data source plugin:

        class MyCollector(BaseCollector):
            @property
            def meta(self) -> PluginMeta:
                return PluginMeta(name="my-source", source_type="custom")

            async def search(self, query: str, max_results: int = 20, **kwargs) -> list[SearchResult]:
                # Implement search logic
                return [SearchResult(url="...", title="...", snippet="...")]

    The plugin will be auto-discovered if placed in the plugins directory
    or registered via PluginManager.register().
    """

    @property
    @abc.abstractmethod
    def meta(self) -> PluginMeta:
        """Return plugin metadata."""
        ...

    @abc.abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 20,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Search for resources.

        Args:
            query: search query string
            max_results: maximum number of results to return
            **kwargs: additional parameters (e.g. since_days, language)

        Returns:
            List of SearchResult objects.
        """
        ...

    async def fetch(self, url: str, **kwargs: Any) -> str | None:
        """Fetch full content from a URL (optional override).

        Args:
            url: the URL to fetch

        Returns:
            Full text content, or None if not supported.
        """
        return None

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """Validate plugin-specific configuration.

        Args:
            config: plugin configuration dict

        Returns:
            List of error messages (empty = valid).
        """
        return []

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.meta.name!r}>"
