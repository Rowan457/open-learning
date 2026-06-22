"""LLM client — wraps MiMo API (OpenAI compatible) with retry, cost tracking, tracing."""

from __future__ import annotations

import json as _json
from typing import Any

from openlearning.log import get_logger

logger = get_logger("LLM")

# Lazy-initialized singletons
_client = None
_async_client = None
_tracing_initialized = False


def _ensure_tracing() -> None:
    """Initialize LangSmith tracing once."""
    global _tracing_initialized
    if _tracing_initialized:
        return
    _tracing_initialized = True
    try:
        from openlearning.monitoring.tracer import init_tracing
        result = init_tracing()
        if result.get("enabled"):
            logger.info("LangSmith tracing enabled: %s", result.get("project", ""))
    except Exception as e:
        logger.debug("Tracing init skipped: %s", e)


def _get_client():
    """Get an OpenAI-compatible client for MiMo."""
    global _client
    if _client is None:
        from openai import OpenAI
        from openlearning.config import get_config
        config = get_config()
        _client = OpenAI(api_key=config.llm.api_key, base_url=config.llm.base_url)
    return _client


def _get_async_client():
    """Get an async OpenAI-compatible client for MiMo."""
    global _async_client
    if _async_client is None:
        from openai import AsyncOpenAI
        from openlearning.config import get_config
        config = get_config()
        _async_client = AsyncOpenAI(api_key=config.llm.api_key, base_url=config.llm.base_url)
    return _async_client


def get_model(tier: str = "standard") -> str:
    """Get model ID by tier: pro / standard / lite."""
    from openlearning.config import get_config
    config = get_config()
    models = config.llm.models
    return {"pro": models.pro, "standard": models.standard, "lite": models.lite}.get(tier, models.standard)


def _record_cost(model: str, input_tokens: int, output_tokens: int) -> None:
    """Record cost via CostTracker."""
    try:
        from openlearning.monitoring.cost import get_tracker
        tracker = get_tracker()
        tracker.record_call(model, input_tokens, output_tokens)
        if tracker.should_warn():
            logger.warning("Cost approaching limit: $%.2f / $%.2f", tracker.daily_cost, tracker.daily_limit)
        if tracker.is_over_limit():
            logger.error("Cost limit exceeded: $%.2f / $%.2f", tracker.daily_cost, tracker.daily_limit)
    except Exception:
        pass  # Cost tracking is non-critical


def chat(
    messages: list[dict],
    model: str | None = None,
    tier: str = "standard",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    response_format: dict | None = None,
) -> str:
    """Synchronous chat completion with retry and cost tracking."""
    _ensure_tracing()
    client = _get_client()
    model_id = model or get_model(tier)

    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    try:
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
        from openai import APITimeoutError, APIConnectionError, RateLimitError

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((APITimeoutError, APIConnectionError, RateLimitError)),
            reraise=True,
        )
        def _call():
            return client.chat.completions.create(**kwargs)

        resp = _call()

        # Record cost
        if hasattr(resp, 'usage') and resp.usage:
            _record_cost(model_id, resp.usage.prompt_tokens, resp.usage.completion_tokens)

        return resp.choices[0].message.content or ""

    except Exception as e:
        logger.error("LLM call failed (model=%s): %s", model_id, e)
        return ""


async def achat(
    messages: list[dict],
    model: str | None = None,
    tier: str = "standard",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    response_format: dict | None = None,
) -> str:
    """Async chat completion with retry and cost tracking."""
    _ensure_tracing()
    client = _get_async_client()
    model_id = model or get_model(tier)

    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    try:
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
        from openai import APITimeoutError, APIConnectionError, RateLimitError

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((APITimeoutError, APIConnectionError, RateLimitError)),
            reraise=True,
        )
        async def _call():
            return await client.chat.completions.create(**kwargs)

        resp = await _call()

        # Record cost
        if hasattr(resp, 'usage') and resp.usage:
            _record_cost(model_id, resp.usage.prompt_tokens, resp.usage.completion_tokens)

        return resp.choices[0].message.content or ""

    except Exception as e:
        logger.error("LLM async call failed (model=%s): %s", model_id, e)
        return ""


def chat_json(
    messages: list[dict],
    model: str | None = None,
    tier: str = "standard",
    temperature: float = 0.1,
) -> dict:
    """Chat with JSON output, returns parsed dict. Returns {} on failure."""
    content = chat(
        messages=messages,
        model=model,
        tier=tier,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    if not content:
        return {}
    try:
        return _json.loads(content)
    except _json.JSONDecodeError as e:
        logger.warning("JSON parse failed: %s (content: %s...)", e, content[:100])
        return {}


async def achat_json(
    messages: list[dict],
    model: str | None = None,
    tier: str = "standard",
    temperature: float = 0.1,
) -> dict:
    """Async chat with JSON output, returns parsed dict. Returns {} on failure."""
    content = await achat(
        messages=messages,
        model=model,
        tier=tier,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    if not content:
        return {}
    try:
        return _json.loads(content)
    except _json.JSONDecodeError as e:
        logger.warning("JSON parse failed: %s (content: %s...)", e, content[:100])
        return {}
