"""Obligation tracking agent."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import ObligationTrackingOutput


# Obligation linguistic signals
OBLIGATION_SIGNALS = {
    "obligation": ["shall", "must", "agrees to", "will", "is required to", "undertakes to"],
    "prohibition": ["shall not", "must not", "is prohibited from", "may not", "will not"],
    "condition": ["subject to", "provided that", "unless", "conditional upon", "if"],
}


class ObligationAgent(BaseAgent):
    """Agent for obligation tracking."""

    output_schema = ObligationTrackingOutput
    prompt_file = "prompts/obligation_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> ObligationTrackingOutput:
        """Extract obligations from contract."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Extract all obligations, prohibitions, and conditions",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
        )
