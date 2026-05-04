"""Clause analysis agent."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import ClauseAnalysisOutput


class ClauseAgent(BaseAgent):
    """Agent for clause-by-clause analysis."""

    output_schema = ClauseAnalysisOutput
    prompt_file = "prompts/clause_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> ClauseAnalysisOutput:
        """Benchmark clauses against taxonomy."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Perform a complete clause inventory and benchmark against standard taxonomy",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
            top_k=50,  # Clause analysis often needs more context
        )