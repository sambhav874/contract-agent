"""Red flag detection agent."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import RedFlagOutput


class RedFlagAgent(BaseAgent):
    """Agent for red flag detection with LLM-native pattern recognition."""

    output_schema = RedFlagOutput
    prompt_file = "prompts/redflag_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> RedFlagOutput:
        """Detect red flags in contract with exhaustive retrieval."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Identify all red flags, missing standard clauses, unusual terms, one-sided provisions, and hidden risks. Flag anything a senior lawyer would highlight before signing.",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
            top_k=80,
        )
