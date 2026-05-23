"""Obligation tracking agent."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import ObligationTrackingOutput


class ObligationAgent(BaseAgent):
    """Agent for obligation tracking with LLM-native confidence calibration."""

    output_schema = ObligationTrackingOutput
    prompt_file = "prompts/obligation_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> ObligationTrackingOutput:
        """Extract obligations from contract with exhaustive retrieval."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Extract ALL obligations, prohibitions, conditions, reporting requirements, notice periods, maintenance duties, and operational commitments. For each, identify the responsible party, deadline, trigger condition, and consequence of breach.",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
            top_k=80,
        )
