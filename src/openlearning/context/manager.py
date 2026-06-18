"""Context Manager — token counting and compression."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextWindow:
    """Represents a context window with token tracking."""

    max_tokens: int = 128_000
    warn_threshold: float = 0.70
    compress_threshold: float = 0.85
    critical_threshold: float = 0.95

    # Internal state
    _messages: list[dict] = field(default_factory=list)
    _token_count: int = 0

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the context."""
        tokens = self._estimate_tokens(content)
        self._messages.append({"role": role, "content": content, "tokens": tokens})
        self._token_count += tokens

    def get_usage_ratio(self) -> float:
        """Get current token usage ratio."""
        return self._token_count / self.max_tokens

    def needs_compression(self) -> int:
        """Check if compression is needed. Returns compression level (0-3)."""
        ratio = self.get_usage_ratio()
        if ratio > self.critical_threshold:
            return 3
        elif ratio > self.compress_threshold:
            return 2
        elif ratio > self.warn_threshold:
            return 1
        return 0

    def compress(self, level: int = 1) -> None:
        """Compress context to the specified level."""
        if level >= 1:
            self._sliding_window()
        if level >= 2:
            self._compress_tool_outputs()
        if level >= 3:
            self._decision_log()

    def _sliding_window(self) -> None:
        """L1: Keep last 5 messages, summarize earlier ones."""
        if len(self._messages) <= 5:
            return

        # Summarize older messages
        old = self._messages[:-5]
        recent = self._messages[-5:]

        summary = f"[Previous {len(old)} messages summarized]"
        self._messages = [{"role": "system", "content": summary, "tokens": 50}] + recent
        self._recalculate_tokens()

    def _compress_tool_outputs(self) -> None:
        """L2: Compress tool outputs to key results only."""
        for msg in self._messages:
            content = msg.get("content", "")
            if len(content) > 1000:
                # Keep first 200 + last 200 chars
                msg["content"] = content[:200] + "\n... [compressed] ...\n" + content[-200:]
        self._recalculate_tokens()

    def _decision_log(self) -> None:
        """L3: Replace all history with structured decision log."""
        summary = f"[Context compressed: {len(self._messages)} messages → decision log]"
        self._messages = [{"role": "system", "content": summary, "tokens": 100}]
        self._recalculate_tokens()

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 chars for English, 2 chars for Chinese)."""
        cn_chars = sum(1 for c in text if ord(c) > 0x4E00)
        en_chars = len(text) - cn_chars
        return cn_chars // 2 + en_chars // 4

    def _recalculate_tokens(self) -> None:
        """Recalculate total token count."""
        self._token_count = sum(msg.get("tokens", 0) for msg in self._messages)

    def get_messages(self) -> list[dict]:
        """Get current messages."""
        return self._messages

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        self._token_count = 0
