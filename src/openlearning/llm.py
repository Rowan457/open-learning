"""LLM client — wraps MiMo API (OpenAI compatible) with model tiering."""

from __future__ import annotations

from typing import Any

from openlearning.config import get_config


def _get_client():
    """Get an OpenAI-compatible client for MiMo."""
    from openai import OpenAI

    config = get_config()
    return OpenAI(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
    )


def _get_async_client():
    """Get an async OpenAI-compatible client for MiMo."""
    from openai import AsyncOpenAI

    config = get_config()
    return AsyncOpenAI(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
    )


def get_model(tier: str = "standard") -> str:
    """Get model ID by tier: pro / standard / lite."""
    config = get_config()
    models = config.llm.models
    return {
        "pro": models.pro,
        "standard": models.standard,
        "lite": models.lite,
    }.get(tier, models.standard)


def chat(
    messages: list[dict],
    model: str | None = None,
    tier: str = "standard",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    response_format: dict | None = None,
) -> str:
    """Synchronous chat completion.

    Args:
        messages: [{"role": "system/user/assistant", "content": "..."}]
        model: Model ID (overrides tier)
        tier: Model tier: pro/standard/lite
        temperature: Sampling temperature
        max_tokens: Max output tokens
        response_format: {"type": "json_object"} for JSON mode

    Returns:
        Assistant message content string.
    """
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

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def achat(
    messages: list[dict],
    model: str | None = None,
    tier: str = "standard",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    response_format: dict | None = None,
) -> str:
    """Async chat completion."""
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

    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def chat_json(
    messages: list[dict],
    model: str | None = None,
    tier: str = "standard",
    temperature: float = 0.1,
) -> dict:
    """Chat with JSON output, returns parsed dict."""
    import json

    content = chat(
        messages=messages,
        model=model,
        tier=tier,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return json.loads(content)


async def achat_json(
    messages: list[dict],
    model: str | None = None,
    tier: str = "standard",
    temperature: float = 0.1,
) -> dict:
    """Async chat with JSON output, returns parsed dict."""
    import json

    content = await achat(
        messages=messages,
        model=model,
        tier=tier,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return json.loads(content)
