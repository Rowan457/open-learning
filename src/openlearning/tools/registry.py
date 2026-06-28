"""Skill registry — discovers and manages Skill modules."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool


@dataclass
class SkillInfo:
    """Metadata for a registered skill."""

    name: str
    module_path: str
    tools: list[BaseTool] = field(default_factory=list)
    enabled: bool = True


class SkillRegistry:
    """Central registry for all Skill modules."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillInfo] = {}

    def register(self, name: str, module_path: str, enabled: bool = True) -> None:
        """Register a skill by its module path."""
        self._skills[name] = SkillInfo(
            name=name,
            module_path=module_path,
            enabled=enabled,
        )

    def load(self, name: str) -> list[BaseTool]:
        """Import the skill module and return its tools."""
        info = self._skills.get(name)
        if info is None:
            raise KeyError(f"Skill '{name}' not registered")

        if not info.enabled:
            return []

        if info.tools:
            return info.tools

        mod = importlib.import_module(info.module_path)
        # Convention: each module exports a TOOLS list or a get_tools() function
        if hasattr(mod, "get_tools"):
            info.tools = mod.get_tools()
        elif hasattr(mod, "TOOLS"):
            info.tools = list(mod.TOOLS)
        else:
            # Fallback: collect all @tool-decorated callables
            info.tools = [
                obj
                for obj in vars(mod).values()
                if isinstance(obj, BaseTool)
            ]

        return info.tools

    def load_all(self) -> dict[str, list[BaseTool]]:
        """Load all enabled skills and return name→tools mapping."""
        result: dict[str, list[BaseTool]] = {}
        for name in self._skills:
            try:
                tools = self.load(name)
                if tools:
                    result[name] = tools
            except Exception:
                # Skip skills that fail to load
                continue
        return result

    def get_all_tools(self) -> list[BaseTool]:
        """Flat list of all tools from all enabled skills."""
        tools: list[BaseTool] = []
        for skill_tools in self.load_all().values():
            tools.extend(skill_tools)
        return tools

    def list_skills(self) -> list[SkillInfo]:
        """List all registered skills."""
        return list(self._skills.values())


# Global singleton
registry = SkillRegistry()
