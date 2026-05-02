"""Risk analysis agent."""

from typing import Any

from app.config import settings
from app.agents.base_agent import BaseAgent
from app.db.models import RiskAnalysisOutput


class RiskAgent(BaseAgent):
    """Agent for risk analysis."""

    output_schema = RiskAnalysisOutput
    prompt_file = "prompts/risk_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> RiskAnalysisOutput:
        """Analyze contract risks."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Identify all legal and financial risks in this contract",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
        )


def auto_flag_conditions(risks: list[dict]) -> list[str]:
    """Auto-flag items for human review."""
    flags = []

    for risk in risks:
        text = risk.get("clause_text", "").lower()

        # Absent liability cap
        if "liability" in text and "cap" not in text and "limit" not in text:
            flags.append("Absent liability cap")

        # Uncapped indemnification
        if "indemnif" in text and "uncapped" in text:
            flags.append("Uncapped indemnification")

