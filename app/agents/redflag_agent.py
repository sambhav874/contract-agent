"""Red flag detection agent."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import RedFlagOutput


# Red flag patterns
RED_FLAG_PATTERNS = {
    "critical": [
        "unlimited liability",
        "uncapped indemnity",
        "automatic renewal",
        "unilateral termination",
        "ip ownership transfer",
    ],
    "high": [
        "governing law outside major jurisdiction",
        "mandatory arbitration",
        "liquidated damages",
        "non-compete",
    ],
    "medium": [
        "auto-renewal",
        "price increase without consent",
        "limited warranty",
    ],
}


class RedFlagAgent(BaseAgent):
    """Agent for red flag detection."""

    output_schema = RedFlagOutput
    prompt_file = "prompts/redflag_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> RedFlagOutput:
        """Detect red flags in contract."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Identify all red flags, missing clauses, and unusual terms",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
        )
