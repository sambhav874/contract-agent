"""Risk analysis agent."""

from typing import Any

from app.config import settings
from app.agents.base_agent import BaseAgent
from app.db.models import RiskAnalysisOutput


class RiskAgent(BaseAgent):
    """Agent for risk analysis with LLM-native confidence calibration."""

    output_schema = RiskAnalysisOutput
    prompt_file = "prompts/risk_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> RiskAnalysisOutput:
        """Analyze contract risks with exhaustive retrieval."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Identify all legal, financial, operational, and reputational risks. For every risk, determine severity, exposed party, mitigation options, and confidence level based on how directly the source clause supports the finding.",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
            top_k=80,
        )
