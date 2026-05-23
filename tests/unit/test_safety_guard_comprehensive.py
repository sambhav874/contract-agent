"""Comprehensive parameterized safety guard tests.

Targets every conditional branch in SafetyGuard that is not already
exhaustively covered in test_safety_guard.py.
"""

import pytest
import re as _re
from unittest.mock import patch

from app.agents.safety import SafetyGuard


class TestShouldHalt:
    """Iterate over every halting condition exactly once."""

    @pytest.mark.parametrize(
        "config,iteration,expected_halt,expected_substring,pre_seed_cost",
        [
            # cost cap halts (expensive call pre-seeded)
            ({"max_cost_usd": 0.0001, "max_iterations": 100}, 1, True, "Cost cap", True),
            # iteration cap halts
            ({"max_iterations": 5}, 5, True, "Max iterations", False),
            # within limits allows
            ({"max_cost_usd": 10.0, "max_iterations": 10}, 2, False, "", False),
            # cost cap landed exactly on boundary
            ({"max_cost_usd": 0.0, "max_iterations": 10}, 1, True, "Cost cap", True),
        ],
    )
    def test_should_halt_parametrized(self, config, iteration, expected_halt, expected_substring, pre_seed_cost):
        guard = SafetyGuard(config)
        if pre_seed_cost:
            # force cost above cap so it triggers
            guard.track_cost("gemini", 10_000_000, 10_000_000)
        halt, reason = guard.should_halt([], iteration)
        assert halt is expected_halt
        if expected_substring:
            assert expected_substring in reason


class TestMaxTokensPerRequest:
    """max_tokens_per_request is stored but currently unused in SafetyGuard.
    This test documents the contract so any future enforcement is covered."""

    def test_max_tokens_per_request_stored(self):
        guard = SafetyGuard({"max_tokens_per_request": 2048})
        assert guard.max_tokens_per_request == 2048


class TestForbiddenPatterns:
    """Every regex in FORBIDDEN_PATTERNS must trigger on a realistic payload."""

    @pytest.mark.parametrize(
        "pattern,payload",
        [
            (r"rm\s+-rf\s+/", {"cmd": "rm -rf /"}),
            (r"DROP\s+TABLE", {"query": "DROP TABLE contracts"}),
            (r"format\s+[A-Z]:", {"disk": "format C:"}),
        ],
    )
    def test_builtin_forbidden(self, pattern, payload):
        guard = SafetyGuard({})
        # use the built-in patterns
        tool_input = payload
        safe, reason = guard.validate_tool_call("exec", tool_input)
        assert not safe
        assert "Forbidden" in reason

    def test_custom_forbidden_override(self):
        guard = SafetyGuard({"forbidden_patterns": [r"password\d+"]})
        safe, reason = guard.validate_tool_call("exec", {"input": "password123"})
        assert not safe
        assert "Forbidden" in reason

    def test_no_false_positives_on_safe_input(self):
        guard = SafetyGuard({})
        safe, _ = guard.validate_tool_call("search", {"query": "normal query"})
        assert safe


class TestRequiresHumanApproval:
    """Parametrize over every tool in the default require list."""

    @pytest.mark.parametrize(
        "tool_name,expected",
        [
            ("send_email", True),
            ("delete_contract", True),
            ("bulk_update", True),
            ("search", False),
            ("summarize_contract", False),
        ],
    )
    def test_human_approval(self, tool_name, expected):
        guard = SafetyGuard({})
        assert guard.requires_human_approval(tool_name) is expected

    def test_custom_human_approval_list(self):
        guard = SafetyGuard({"require_human_approval": ["deploy_code"]})
        assert guard.requires_human_approval("deploy_code")
        assert not guard.requires_human_approval("search")


class TestCostTracking:
    """Verify per-model pricing math and cumulative tracking."""

    def test_track_cost_gemini_flash(self):
        guard = SafetyGuard({})
        cost = guard.track_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
        expected = (1_000_000 * 0.15 / 1_000_000) + (1_000_000 * 0.60 / 1_000_000)
        assert cost == pytest.approx(expected, abs=1e-9)
        assert guard.cost_tracker == pytest.approx(expected, abs=1e-9)

    def test_track_cost_unknown_model_falls_back(self):
        guard = SafetyGuard({})
        cost = guard.track_cost("unknown-model", 1_000_000, 1_000_000)
        # Falls back to default pricing (same as gemini-2.5-flash)
        expected = (1_000_000 * 0.15 / 1_000_000) + (1_000_000 * 0.60 / 1_000_000)
        assert cost == pytest.approx(expected, abs=1e-9)

    def test_get_status_format(self):
        guard = SafetyGuard({"max_cost_usd": 5.0, "max_iterations": 15})
        guard.track_cost("gemini", 1_000_000, 500_000)
        status = guard.get_status()
        assert "cost_tracker" in status
        assert "accumulated_cost" in status
        assert "max_cost_usd" in status
        assert "iterations_used" in status
        assert "max_iterations" in status
        assert status["max_cost_usd"] == 5.0
        assert status["max_iterations"] == 15
