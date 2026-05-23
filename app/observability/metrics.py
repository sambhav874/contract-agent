"""Metrics and cost tracking."""

from typing import Any


class CostTracker:
    """Track LLM costs per run."""

    # Pricing per 1M tokens (Gemini 2.5 Flash preview)
    PRICING = {
        "gemini-2.5-flash-preview-05-20": {"input": 0.15, "output": 0.60},
        "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    }

    def __init__(self) -> None:
        self.total_cost = 0.0
        self.calls: list[dict[str, Any]] = []

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> float:
        pricing = self.PRICING.get(model, {"input": 0.15, "output": 0.60})
        input_cost = input_tokens * pricing["input"] / 1_000_000
        output_cost = output_tokens * pricing["output"] / 1_000_000
        total = input_cost + output_cost
        self.total_cost += total
        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "cost_usd": round(total, 8),
        })
        return total

    def get_status(self) -> dict[str, Any]:
        return {
            "total_cost_usd": round(self.total_cost, 6),
            "total_calls": len(self.calls),
            "calls": self.calls,
        }
