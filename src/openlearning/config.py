"""Configuration management using Pydantic Settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ── LLM Model Configuration ──────────────────────────────────

class LLMModels(BaseModel):
    """Model IDs for the three tiers."""

    pro: str = "mimo-v2.5-pro"
    standard: str = "mimo-v2.5"
    lite: str = "mimo-7b"


class LLMRouting(BaseModel):
    """Task → model tier mapping."""

    supervisor: str = "pro"
    planner: str = "pro"
    collector: str = "lite"
    analyzer_extract: str = "standard"
    analyzer_tag: str = "lite"
    analyzer_summarize: str = "lite"
    evaluator: str = "lite"
    tool_router: str = "standard"
    reflector: str = "pro"
    builder: str = "lite"


class LLMCost(BaseModel):
    """Cost per 1M tokens for each model tier."""

    mimo_v2_5_pro: float = Field(15.0, alias="mimo-v2.5-pro")
    mimo_v2_5: float = Field(5.0, alias="mimo-v2.5")
    mimo_7b: float = Field(0.5, alias="mimo-7b")

    model_config = {"populate_by_name": True}


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "mimo"
    api_key: str = ""
    base_url: str = "https://api.mimo.ai/v1"
    models: LLMModels = LLMModels()
    routing: LLMRouting = LLMRouting()
    max_tokens: int = 4096
    temperature: float = 0.3
    cache: bool = True
    retry_max: int = 3
    cost: LLMCost = LLMCost()


# ── Skill Configuration ──────────────────────────────────────

class SearchProviderConfig(BaseModel):
    """Configuration for a single search provider."""

    api_key: str = ""
    daily_limit: int = 100
    enabled: bool = True


class SearchSkillConfig(BaseModel):
    """Search skill configuration."""

    module: str = "openlearning.skills.search"
    enabled: bool = True
    providers: dict[str, SearchProviderConfig] = {}


class FetchSkillConfig(BaseModel):
    """Fetch skill configuration."""

    module: str = "openlearning.skills.fetch"
    enabled: bool = True
    timeout: int = 30
    respect_robots: bool = True


class GenericSkillConfig(BaseModel):
    """Generic skill configuration."""

    module: str = ""
    enabled: bool = True


class SkillsConfig(BaseModel):
    """All skills configuration."""

    search: SearchSkillConfig = SearchSkillConfig()
    fetch: FetchSkillConfig = FetchSkillConfig()
    analyze: GenericSkillConfig = GenericSkillConfig(module="openlearning.skills.analyze")
    persist: GenericSkillConfig = GenericSkillConfig(module="openlearning.skills.persist")
    render: GenericSkillConfig = GenericSkillConfig(module="openlearning.skills.render")
    memory: GenericSkillConfig = GenericSkillConfig(module="openlearning.skills.memory")


# ── Site Configuration ───────────────────────────────────────

class SiteConfig(BaseModel):
    """Static site generation configuration."""

    theme: str = "default"
    language: str = "zh-CN"
    base_url: str = "/"
    favicon: str | None = None
    analytics: str | None = None


# ── Update Configuration ─────────────────────────────────────

class UpdatesConfig(BaseModel):
    """Resource update checking configuration."""

    check_interval: str = "weekly"
    notify: bool = True
    auto_regenerate: bool = True


# ── LangSmith Configuration ──────────────────────────────────

class LangSmithTracing(BaseModel):
    """LangSmith tracing configuration."""

    level: str = "all"  # all / llm_only / off
    capture_inputs: bool = True
    capture_outputs: bool = True


class LangSmithEvaluation(BaseModel):
    """LangSmith evaluation configuration."""

    auto_evaluate: bool = False
    sample_rate: float = 0.1


class LangSmithAlerts(BaseModel):
    """LangSmith cost alerts."""

    daily_cost_limit: float = 10.0
    warn_at: float = 8.0


class LangSmithConfig(BaseModel):
    """LangSmith observability configuration."""

    enabled: bool = True
    api_key: str = ""
    project: str = "openlearning"
    tracing: LangSmithTracing = LangSmithTracing()
    evaluation: LangSmithEvaluation = LangSmithEvaluation()
    alerts: LangSmithAlerts = LangSmithAlerts()


# ── Main Configuration ───────────────────────────────────────

class OpenLearningConfig(BaseSettings):
    """Root configuration for OpenLearning."""

    version: str = "1.0"
    llm: LLMConfig = LLMConfig()
    skills: SkillsConfig = SkillsConfig()
    site: SiteConfig = SiteConfig()
    updates: UpdatesConfig = UpdatesConfig()
    langsmith: LangSmithConfig = LangSmithConfig()

    # Database
    db_path: str = "data/openlearning.db"

    # Output
    output_dir: str = "output"

    model_config = {"env_prefix": "OPENLEARNING_", "env_nested_delimiter": "__"}


# ── Configuration Loading ────────────────────────────────────

_config: OpenLearningConfig | None = None


def load_config(config_path: str | Path | None = None) -> OpenLearningConfig:
    """Load configuration from .env, YAML file, and environment variables.

    Priority: env vars > .env file > YAML file > defaults.
    """
    global _config

    # Load .env file (silently skip if not found)
    load_dotenv(override=False)

    data: dict[str, Any] = {}

    # Try to find config file
    if config_path is None:
        candidates = [
            Path("openlearning.yaml"),
            Path("openlearning.yml"),
            Path.home() / ".openlearning" / "config.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = candidate
                break

    # Load YAML if found
    if config_path and Path(config_path).exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    # Environment variable overrides
    env_overrides = _collect_env_overrides()
    _deep_merge(data, env_overrides)

    _config = OpenLearningConfig(**data)
    return _config


def get_config() -> OpenLearningConfig:
    """Get the current configuration, loading defaults if not yet loaded."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _collect_env_overrides() -> dict[str, Any]:
    """Collect configuration overrides from environment variables."""
    overrides: dict[str, Any] = {}

    # API keys
    if key := os.environ.get("MIMO_API_KEY"):
        overrides.setdefault("llm", {})["api_key"] = key
    if url := os.environ.get("MIMO_BASE_URL"):
        overrides.setdefault("llm", {})["base_url"] = url
    if key := os.environ.get("GOOGLE_API_KEY"):
        overrides.setdefault("skills", {}).setdefault("search", {}).setdefault("providers", {})[
            "google"
        ] = {"api_key": key}
    if key := os.environ.get("YOUTUBE_API_KEY"):
        overrides.setdefault("skills", {}).setdefault("search", {}).setdefault("providers", {})[
            "youtube"
        ] = {"api_key": key}
    if token := os.environ.get("GITHUB_TOKEN"):
        overrides.setdefault("skills", {}).setdefault("search", {}).setdefault("providers", {})[
            "github"
        ] = {"api_key": token}
    if key := os.environ.get("LANGSMITH_API_KEY"):
        overrides.setdefault("langsmith", {})["api_key"] = key

    return overrides


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
