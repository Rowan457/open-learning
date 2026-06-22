"""Cost tracking and alerts for LLM usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CostTracker:
    """Track LLM API costs."""

    daily_limit: float = 10.0
    warn_at: float = 8.0

    # Internal tracking
    _daily_cost: float = 0.0
    _calls: list[dict] = field(default_factory=list)

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> None:
        """Record an LLM API call."""
        self._daily_cost += cost
        self._calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_daily_cost(self) -> float:
        """Get today's total cost."""
        return self._daily_cost

    def is_over_limit(self) -> bool:
        """Check if daily cost limit is exceeded."""
        return self._daily_cost >= self.daily_limit

    def should_warn(self) -> bool:
        """Check if approaching daily limit."""
        return self._daily_cost >= self.warn_at

    def get_summary(self) -> dict[str, Any]:
        """Get cost summary."""
        return {
            "daily_cost": round(self._daily_cost, 4),
            "daily_limit": self.daily_limit,
            "calls_today": len(self._calls),
            "over_limit": self.is_over_limit(),
            "warning": self.should_warn(),
        }


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for an LLM call.

    Prices per 1M tokens (from config).
    """
    price_map = {
        "mimo-v2.5-pro": 15.0,
        "mimo-v2.5": 5.0,
        "mimo-7b": 0.5,
    }

    price = price_map.get(model, 5.0)
    return (input_tokens + output_tokens) / 1_000_000 * price


# Global tracker
_tracker: CostTracker | None = None


def get_tracker() -> CostTracker:
    """Get the global cost tracker."""
    global _tracker
    if _tracker is None:
        from openlearning.config import get_config

        config = get_config()
        _tracker = CostTracker(
            daily_limit=config.langsmith.alerts.daily_cost_limit,
            warn_at=config.langsmith.alerts.warn_at,
        )
    return _tracker
