"""Tests for Planner and planning logic."""

import pytest
from unittest.mock import patch, AsyncMock

from app.agents.planner import Planner


class TestPlanner:
    @pytest.mark.asyncio
    async def test_decompose_returns_steps(self):
        planner = Planner()
        with patch("app.agents.planner.call_gemini", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = [
                {"step_id": "1", "description": "Find penalty clause", "tools_needed": ["search_contract_clauses"], "depends_on": [], "success_criteria": "Clause found", "fallback": "Ask user"},
                {"step_id": "2", "description": "Check KPI thresholds", "tools_needed": ["get_kpi_registry"], "depends_on": ["1"], "success_criteria": "KPIs listed", "fallback": "Direct answer"},
            ]
            result = await planner.decompose("What are the penalties and KPIs?")
            assert len(result) == 2
            assert result[0]["step_id"] == "1"

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_error(self):
        planner = Planner()
        with patch("app.agents.planner.call_gemini", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM error")
            result = await planner.decompose("Some question")
            assert len(result) == 1
            assert result[0]["step_id"] == "1"

    @pytest.mark.asyncio
    async def test_decompose_returns_dict(self):
        planner = Planner()
        with patch("app.agents.planner.call_gemini", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {"steps": [{"step_id": "1", "description": "test"}]}
            result = await planner.decompose("test goal")
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_maybe_replan(self):
        planner = Planner()
        with patch("app.agents.planner.call_gemini", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {"replan": False, "reason": "No change needed"}
            messages, reason = await planner.maybe_replan([{"role": "user", "content": "test"}], "original goal")
            assert "No replan" in reason

    @pytest.mark.asyncio
    async def test_maybe_replan_triggers(self):
        planner = Planner()
        with patch("app.agents.planner.call_gemini", new_callable=AsyncMock) as mock_llm:
            def side_effect(*args, **kwargs):
                system_prompt = kwargs.get("system_prompt", args[1] if len(args) > 1 else "")
                if "planning critic" in system_prompt:
                    return {"replan": True, "reason": "Plan outdated", "new_plan": [{"step_id": "1", "description": "new plan", "tools_needed": [], "depends_on": [], "success_criteria": "done", "fallback": "ask"}]}
                # decompose call
                return {"steps": [{"step_id": "1", "description": "new plan", "tools_needed": [], "depends_on": [], "success_criteria": "done", "fallback": "ask"}]}
            mock_llm.side_effect = side_effect
            messages, reason = await planner.maybe_replan([{"role": "user", "content": "test"}], "original goal")
            assert "Replanning" in reason
