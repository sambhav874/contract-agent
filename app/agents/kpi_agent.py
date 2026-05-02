"""KPI extraction agent."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import KPIExtractionOutput


class KPIAgent(BaseAgent):
    """Agent for KPI extraction."""

    output_schema = KPIExtractionOutput
    prompt_file = "prompts/kpi_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> KPIExtractionOutput:
        """Extract KPIs from contract."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Extract all KPIs, payment terms, milestones, and deadlines",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
            top_k=40,
        )
