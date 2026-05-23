"""Tests for SafetyGuard."""

import pytest
from app.agents.safety import SafetyGuard


class TestSafetyGuard:
    def test_should_halt_cost_cap(self):
        guard = SafetyGuard({"max_cost_usd": 0.0001, "max_iterations": 100})
        for _ in range(5):
            guard.track_cost("gemini", 100000, 100000)  # ~0.006 per call
        for _ in range(5):
            guard.track_cost("gemini", 100000, 1000000)  # big calls
        halt, reason = guard.should_halt([], 1)
        assert halt
        assert "Cost cap" in reason

    def test_should_halt_max_iterations(self):
        guard = SafetyGuard({"max_iterations": 3})
        halt, reason = guard.should_halt([], 3)
        assert halt
        assert "Max iterations" in reason

    def test_should_not_halt_within_limits(self):
        guard = SafetyGuard({})
        halt, _ = guard.should_halt([], 1)
        assert not halt

    def test_validate_tool_call_forbidden_pattern(self):
        guard = SafetyGuard({"forbidden_patterns": [r"DROP\s+TABLE"]})
        safe, reason = guard.validate_tool_call("query_db", {"query": "DROP TABLE contracts"})
        assert not safe
        assert "Forbidden" in reason

    def test_validate_tool_call_safe(self):
        guard = SafetyGuard({})
        safe, _ = guard.validate_tool_call("search", {"query": "penalty clause"})
        assert safe

    def test_cost_tracking(self):
        guard = SafetyGuard({})
        cost = guard.track_cost("gemini", 1000, 500)
        assert cost > 0
        assert guard.cost_tracker > 0

    def test_requires_human_approval(self):
        guard = SafetyGuard({"require_human_approval": ["delete_contract"]})
        assert guard.requires_human_approval("delete_contract")
        assert not guard.requires_human_approval("search")

    def test_track_cost_multiple_calls(self):
        guard = SafetyGuard({"max_cost_usd": 10.0})
        guard.track_cost("gemini", 1000, 1000)
        initial = guard.cost_tracker
        guard.track_cost("gemini", 2000, 2000)
        assert guard.cost_tracker > initial
