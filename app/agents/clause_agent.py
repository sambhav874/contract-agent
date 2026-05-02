"""Clause analysis agent."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import ClauseAnalysisOutput


# Clause taxonomy by contract type
CLAUSE_TAXONOMY = {
    "NDA": [
        "confidentiality", "non_disclosure", "term", "termination",
        "return_of_materials", "remedies", "no_license"
    ],
    "SaaS": [
        "subscription_terms", "payment", "sla", "data_security",
        "ip_ownership", "limitation_of_liability", "termination", "renewal"
    ],
    "Vendor": [
        "scope_of_work", "payment_terms", "deliverables", "acceptance_criteria",
        "warranty", "indemnification", "limitation_of_liability", "termination"
    ],
    "M&A": [
        "purchase_price", "representations_warranties", "covenants",
        "conditions_precedent", "indemnification", "termination_fee"
    ],
    "Employment": [
        "duties", "compensation", "benefits", "term", "termination",
        "restrictive_covenants", "ip_assignment", "confidentiality"
    ],
}


class ClauseAgent(BaseAgent):
    """Agent for clause analysis."""

    output_schema = ClauseAnalysisOutput
    prompt_file = "prompts/clause_agent/v1.txt"

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> ClauseAnalysisOutput:
        """Analyze contract clauses."""
        return await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Analyze all clauses and identify missing or unusual terms",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
        )
