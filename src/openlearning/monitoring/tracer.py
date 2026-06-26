"""LangSmith tracing initialization and configuration.

提供：
- init_tracing(): 设置环境变量，启用 LangSmith 自动追踪
- traceable: 装饰器，标记需要追踪的函数
- get_trace_url(): 获取运行的 LangSmith 追踪 URL
- get_current_run_id(): 获取当前运行的 ID
"""

from __future__ import annotations

import os
from typing import Any

from openlearning.log import get_logger

logger = get_logger("Tracer")

_initialized = False


def init_tracing() -> dict[str, Any]:
    """Initialize LangSmith tracing if configured.

    设置环境变量后，LangChain 会自动追踪所有 LLM 调用、链和工具。
    需要在任何 LangChain 代码运行前调用。

    Returns {enabled, project}.
    """
    global _initialized
    if _initialized:
        return {"enabled": os.environ.get("LANGCHAIN_TRACING_V2") == "true"}
    _initialized = True

    try:
        from openlearning.config import get_config

        config = get_config()

        if not config.langsmith.enabled:
            logger.info("LangSmith 已禁用")
            return {"enabled": False, "project": config.langsmith.project}

        if not config.langsmith.api_key:
            logger.warning("LangSmith API key 未配置")
            return {"enabled": False, "reason": "No API key configured"}

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = config.langsmith.api_key
        os.environ["LANGCHAIN_PROJECT"] = config.langsmith.project

        # 设置端点（可选，默认使用 LangSmith SaaS）
        if hasattr(config.langsmith, 'endpoint') and config.langsmith.endpoint:
            os.environ["LANGCHAIN_ENDPOINT"] = config.langsmith.endpoint

        logger.info("LangSmith 追踪已启用: project=%s", config.langsmith.project)
        return {
            "enabled": True,
            "project": config.langsmith.project,
        }

    except Exception as e:
        logger.warning("LangSmith 初始化失败: %s", e)
        return {"enabled": False, "reason": str(e)}


def traceable(name: str | None = None):
    """装饰器：为函数添加 LangSmith 追踪。

    如果 langsmith 可用且已启用，使用 @traceable 装饰器。
    否则返回原函数。

    用法:
        @traceable("my_agent")
        async def my_agent(state):
            ...
    """
    try:
        from langsmith import traceable as ls_traceable
        return ls_traceable(name=name)
    except ImportError:
        # langsmith 未安装，返回无操作装饰器
        def noop_decorator(fn):
            return fn
        return noop_decorator


def get_trace_url(run_id: str) -> str:
    """Get the LangSmith trace URL for a run."""
    try:
        from openlearning.config import get_config

        config = get_config()
        project = config.langsmith.project
        return f"https://smith.langchain.com/o/default/projects/p/{project}/r/{run_id}"
    except Exception:
        return ""


def get_current_run_id() -> str | None:
    """Get the current LangSmith run ID (if any)."""
    try:
        from langsmith.run_helpers import get_current_run_tree
        run = get_current_run_tree()
        return str(run.id) if run else None
    except Exception:
        return None
