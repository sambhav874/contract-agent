"""Intent routing and query planning using Gemini Flash."""

from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.db.models import StructuralMap
from app.llm.gemini_client import call_gemini


class QueryPlan(BaseModel):
    """Query plan from intent router."""

    intent: str
    sub_intents: list[str] = Field(default_factory=list)
    priority_section_tags: list[str] = Field(default_factory=list)
    chunk_levels: list[str] = Field(default_factory=list)
    map_pass_required: bool = False
    max_retrieval_rounds: int = 3
    output_schema_name: str = ""
    analysis_mode: str = "plain"


# Intent to section tag mapping
INTENT_TAG_MAP = {
    "risk": ["indemnification", "liability", "warranty", "representation", "termination", "dispute_resolution", "force_majeure", "ip_ownership"],
    "kpi": ["payment", "milestone", "sla", "penalty", "schedule"],
    "clause": [],  # All sections filtered per query
    "obligations": ["covenants", "notice", "termination"],
    "summary": ["recitals", "definitions"],
    "redflags": [],  # ALL sections
    "query": [],  # Determined by router
}

# Intent to chunk levels mapping
INTENT_LEVEL_MAP = {
    "risk": ["meso", "macro"],
    "kpi": ["micro", "meso"],
    "clause": ["meso"],
    "obligations": ["meso", "micro"],
    "summary": ["macro"],
    "redflags": ["macro", "meso"],
    "query": ["meso"],
}

# Intent to output schema mapping
INTENT_SCHEMA_MAP = {
    "risk": "RiskAnalysisOutput",
    "kpi": "KPIExtractionOutput",
    "clause": "ClauseAnalysisOutput",
    "obligations": "ObligationTrackingOutput",
    "summary": "SummaryOutput",
    "redflags": "RedFlagOutput",
}


async def route_intent(
    intent: str,
    user_query: str | None = None,
    structural_map: StructuralMap | None = None,
) -> QueryPlan:
    """
    Route user intent to query plan.

    Args:
        intent: User intent flag
        user_query: Optional free-text query
        structural_map: Contract structural map

    Returns:
        QueryPlan object
    """
    try:
        # Try to use Gemini for intelligent routing
        plan = await _route_with_gemini(intent, user_query, structural_map)
        return plan
    except Exception:
        # Fallback to hardcoded mapping
        return _route_hardcoded(intent, user_query)


async def _route_with_gemini(
    intent: str,
    user_query: str | None,
    structural_map: StructuralMap | None,
) -> QueryPlan:
    """Route intent using Gemini Flash."""
    system_prompt = """You are an intent router for a contract analysis agent.
Your job is to classify the user's intent and create a query plan.

Output a JSON object with:
- intent: The primary intent
- sub_intents: List of related sub-intents
- priority_section_tags: Section types or specific section identifiers to focus on
- chunk_levels: Which chunk levels to retrieve ('macro', 'meso', 'micro')
- max_retrieval_rounds: Number of retrieval iterations (default 3)
- output_schema_name: Name of output schema to use
- analysis_mode: 'plain' or 'legal'

Intent mappings:
- risk: Identify legal/financial risks
- kpi: Extract KPIs, targets, milestones, dates, amounts.
- clause: Analyze specific clauses
- obligations: Track obligations and deadlines
- summary: Generate executive summary
- redflags: Detect red flags and missing clauses
- query: Answer specific question

Use the provided Contract Structure to identify specific section titles or numbers that are likely to contain the requested information and include them in priority_section_tags.
For KPI intent, always prioritize sections like "Article IV", "Performance", "SLA", "Penalty", "Target", "Exhibit", or "Schedule".
"""

    user_message = f"""Intent: {intent}
User Query: {user_query or 'N/A'}
Contract Structure: {structural_map.model_dump_json() if structural_map else 'N/A'}

Create a query plan."""

    response = await call_gemini(
        model=settings.gemini_fast_model,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.0,
    )

    return QueryPlan(
        intent=response.get("intent", intent),
        sub_intents=response.get("sub_intents", []),
        priority_section_tags=response.get("priority_section_tags", []),
        chunk_levels=response.get("chunk_levels", ["meso"]),
        map_pass_required=response.get("map_pass_required", False),
        max_retrieval_rounds=response.get("max_retrieval_rounds", 3),
        output_schema_name=response.get("output_schema_name", ""),
        analysis_mode=response.get("analysis_mode", "plain"),
    )


def _route_hardcoded(intent: str, user_query: str | None = None) -> QueryPlan:
    """Fallback hardcoded routing."""
    tags = INTENT_TAG_MAP.get(intent, [])
    levels = INTENT_LEVEL_MAP.get(intent, ["meso"])
    schema = INTENT_SCHEMA_MAP.get(intent, "")

    # Red flags need map pass
    map_pass = intent == "redflags"

    return QueryPlan(
        intent=intent,
        sub_intents=[],
        priority_section_tags=tags,
        chunk_levels=levels,
        map_pass_required=map_pass,
        max_retrieval_rounds=3,
        output_schema_name=schema,
        analysis_mode="legal" if intent in ["clause", "risk"] else "plain",
    )
