"""Summary generation agent."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import SummaryOutput


class SummaryAgent(BaseAgent):
    """Agent for generating contract summaries with exhaustive retrieval."""

    output_schema = SummaryOutput
    prompt_file = "prompts/summary_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> SummaryOutput:
        """Generate contract summary with comprehensive context."""
        mode = query_plan.analysis_mode if hasattr(query_plan, 'analysis_mode') else 'plain'
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or f"Generate a {mode} English summary of this contract. Cover ALL parties, commercial terms, pricing, penalties, key dates, termination rights, and any unusual or missing provisions.",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
            top_k=80,
        )
