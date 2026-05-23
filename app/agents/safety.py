"""Safety guard for agent operations."""

import json
import re
import time
from typing import Any


class SafetyGuard:
    """Hard limits on what the agent can do. Cannot be overridden by the LLM."""

    FORBIDDEN_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"DROP\s+TABLE",
        r"format\s+[A-Z]:",
    ]

    _accumulated_cost = 0.0
    _total_iterations = 0

    def __init__(self, config: dict[str, Any]) -> None:
        self.max_cost_usd = config.get("max_cost_usd", 5.0)
        self.max_iterations = config.get("max_iterations", 15)
        self.max_tokens_per_request = config.get("max_tokens_per_request", 32768)
        self.require_human_approval_for = config.get(
            "require_human_approval",
            ["send_email", "delete_contract", "bulk_update"],
        )
        self.cost_tracker = 0.0
        self.forbidden_patterns = config.get("forbidden_patterns", self.FORBIDDEN_PATTERNS)

    def should_halt(self, messages: list[Any], iteration: int) -> tuple[bool, str]:
        SafetyGuard._total_iterations = max(SafetyGuard._total_iterations, iteration)
        if self.cost_tracker > self.max_cost_usd:
            return True, f"Cost cap exceeded ($ {self.cost_tracker:.4f} > $ {self.max_cost_usd:.4f})"
        if iteration >= self.max_iterations:
            return True, f"Max iterations reached ({iteration} >= {self.max_iterations})"
        return False, ""

    def requires_human_approval(self, tool_name: str) -> bool:
        return tool_name in self.require_human_approval_for

    def validate_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> tuple[bool, str]:
        input_str = json.dumps(tool_input, default=str)
        for pattern in self.forbidden_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return False, f"Forbidden pattern detected: {pattern}"
        return True, ""

    def track_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        # Gemini 2.5 Flash pricing (hypothetical per 1M tokens)
        # Input: $0.15 / 1M, Output: $0.60 / 1M
        input_cost = input_tokens * 0.15 / 1_000_000
        output_cost = output_tokens * 0.60 / 1_000_000
        total = input_cost + output_cost
        self.cost_tracker += total
        SafetyGuard._accumulated_cost += total
        return total

    def get_status(self) -> dict[str, Any]:
        return {
            "cost_tracker": round(self.cost_tracker, 6),
            "accumulated_cost": round(SafetyGuard._accumulated_cost, 6),
            "max_cost_usd": self.max_cost_usd,
            "iterations_used": SafetyGuard._total_iterations,
            "max_iterations": self.max_iterations,
        }
