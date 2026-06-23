"""Plugin system — user-extensible collectors and tools.

Provides:
- BaseCollector: abstract base for custom data source collectors
- PluginManager: discovery, loading, and lifecycle management
- YAML-based plugin configuration
"""

from openlearning.plugins.base import BaseCollector
from openlearning.plugins.manager import PluginManager

__all__ = ["BaseCollector", "PluginManager"]
