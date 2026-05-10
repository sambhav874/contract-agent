"""Intent routing and query planning — structural-map-aware version."""

from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.db.models import StructuralMap
from app.llm.gemini_client import call_gemini


class QueryPlan(BaseModel):
    """Query plan produced by the intent router."""

    intent: str
    sub_intents: list[str] = Field(default_factory=list)
    priority_section_tags: list[str] = Field(default_factory=list)
    chunk_levels: list[str] = Field(default_factory=list)
    map_pass_required: bool = False
    max_retrieval_rounds: int = 3
    output_schema_name: str = ""
    analysis_mode: str = "plain"


# ── Static fallback mappings ──────────────────────────────────────────

_INTENT_TAGS: dict[str, list[str]] = {
    "risk":        ["indemnification", "liability", "warranty", "representation",
                    "termination", "dispute_resolution", "force_majeure", "ip_ownership"],
    "kpi":         ["payment", "milestone", "sla", "penalty", "schedule"],
    "clause":      [],   # determined dynamically from structural map
    "obligations": ["covenants", "notice", "termination", "payment"],
    "summary":     ["recitals", "definitions"],
    "redflags":    [],   # map pass covers all sections
    "query":       [],
}

_INTENT_LEVELS: dict[str, list[str]] = {
    "risk":        ["meso", "macro"],
    "kpi":         ["micro", "meso", "macro"],
    "clause":      ["meso"],
    "obligations": ["meso", "micro"],
    "summary":     ["macro"],
    "redflags":    ["macro", "meso"],
    "query":       ["meso"],
}

_INTENT_SCHEMA: dict[str, str] = {
    "risk":        "RiskAnalysisOutput",
    "kpi":         "KPIExtractionOutput",
    "clause":      "ClauseAnalysisOutput",
    "obligations": "ObligationTrackingOutput",
    "summary":     "SummaryOutput",
    "redflags":    "RedFlagOutput",
}

_MAP_PASS_INTENTS = {"redflags", "clause", "summary", "kpi"}


_ROUNDS: dict[str, int] = {
    "risk":        3,
    "kpi":         4,
    "clause":      3,
    "obligations": 3,
    "summary":     2,
    "redflags":    3,
    "query":       2,
}


# ── Public entry point ────────────────────────────────────────────────

async def route_intent(
    intent: str,
    user_query: str | None = None,
    structural_map: StructuralMap | None = None,
) -> QueryPlan:
    """
    Route user intent to a QueryPlan.

    Tries Gemini Flash for intelligent routing; falls back to hardcoded
    mappings augmented with structural-map section titles.
    """
    # Always extract structural hints — even for the hardcoded fallback
    structural_hints = _extract_structural_hints(intent, structural_map)

    try:
        plan = await _route_with_gemini(intent, user_query, structural_map, structural_hints)
        # Ensure structural hints are always included (Gemini may miss them)
        plan.priority_section_tags = _merge_tags(plan.priority_section_tags, structural_hints)
        return plan
    except Exception:
        return _route_hardcoded(intent, user_query, structural_hints)


# ── Gemini routing ────────────────────────────────────────────────────

async def _route_with_gemini(
    intent: str,
    user_query: str | None,
    structural_map: StructuralMap | None,
    structural_hints: list[str],
) -> QueryPlan:
    """Use Gemini Flash to build an intelligent query plan."""
    try:
        with open("prompts/intent_router/v2.txt", "r") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        system_prompt = _fallback_router_system_prompt()

    # Compact section list for context (avoid large payloads)
    section_list = ""
    if structural_map:
        sections = structural_map.sections[:80]   # cap at 80 sections
        lines = [
            f"  level={s.level} | id={s.section_id[:20]} | title={s.title[:60]}"
            for s in sections
        ]
        section_list = "CONTRACT SECTIONS:\n" + "\n".join(lines)

    user_message = (
        f"INTENT: {intent}\n"
        f"USER QUERY: {user_query or 'N/A'}\n"
        f"STRUCTURAL HINTS FROM MAP: {structural_hints}\n\n"
        f"{section_list}\n\n"
        "Produce the QueryPlan JSON."
    )

    response = await call_gemini(
        model=settings.gemini_fast_model,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.0,
    )

    max_rounds = int(response.get("max_retrieval_rounds", _ROUNDS.get(intent, 3)))
    if intent == "kpi" and max_rounds < 3:
        max_rounds = 3

    # Normalize chunk levels to match our schema (macro, meso, micro)
    raw_levels = response.get("chunk_levels", _INTENT_LEVELS.get(intent, ["meso"]))
    valid_levels = {"macro", "meso", "micro"}
    normalized_levels = []
    for lvl in raw_levels:
        lvl_lower = lvl.lower()
        if lvl_lower in valid_levels:
            normalized_levels.append(lvl_lower)
        elif "section" in lvl_lower or "article" in lvl_lower:
            normalized_levels.append("macro")
        elif "clause" in lvl_lower or "provision" in lvl_lower:
            normalized_levels.append("meso")
        elif "sentence" in lvl_lower or "paragraph" in lvl_lower or "item" in lvl_lower:
            normalized_levels.append("micro")
    
    if not normalized_levels:
        normalized_levels = _INTENT_LEVELS.get(intent, ["meso"])

    return QueryPlan(
        intent=response.get("intent", intent),
        sub_intents=response.get("sub_intents", []),
        priority_section_tags=response.get("priority_section_tags", []),
        chunk_levels=normalized_levels,
        map_pass_required=response.get("map_pass_required", intent in _MAP_PASS_INTENTS),
        max_retrieval_rounds=max_rounds,
        output_schema_name=response.get("output_schema_name", _INTENT_SCHEMA.get(intent, "")),
        analysis_mode=response.get("analysis_mode", "plain"),
    )



# ── Hardcoded fallback ────────────────────────────────────────────────

def _route_hardcoded(
    intent: str,
    user_query: str | None,
    structural_hints: list[str],
) -> QueryPlan:
    """Pure static routing, augmented with structural hints."""
    tags = list(_INTENT_TAGS.get(intent, []))
    tags = _merge_tags(tags, structural_hints)

    return QueryPlan(
        intent=intent,
        sub_intents=[],
        priority_section_tags=tags,
        chunk_levels=_INTENT_LEVELS.get(intent, ["meso"]),
        map_pass_required=intent in _MAP_PASS_INTENTS,
        max_retrieval_rounds=_ROUNDS.get(intent, 3),
        output_schema_name=_INTENT_SCHEMA.get(intent, ""),
        analysis_mode="legal" if intent in {"clause", "risk"} else "plain",
    )


# ── Structural hint extraction ────────────────────────────────────────

def _extract_structural_hints(
    intent: str,
    structural_map: StructuralMap | None,
) -> list[str]:
    """
    Extract relevant section titles/IDs from the structural map based on intent.

    Returns a list of structural path strings that can be added to
    priority_section_tags so the retriever can do targeted structural search.
    """
    if not structural_map:
        return []

    # Keywords that signal relevance per intent
    _INTENT_KEYWORDS: dict[str, list[str]] = {
        "risk":        ["indemnif", "liabilit", "terminat", "warrant", "ip ", "force",
                        "dispute", "arbitrat", "penalty", "damages"],
        "kpi":         ["kpi", "performance", "sla", "penalty", "payment", "price",
                        "exhibit", "schedule", "target", "milestone", "article iv",
                        "article 4", "section 4", "section 3.0", "specification", "standards",
                        "reporting", "audit"],
        "clause":      [],   # all sections
        "obligations": ["shall", "must", "obligat", "covenant", "notice", "report",
                        "payment", "terminat"],
        "summary":     ["recital", "whereas", "article i", "article 1", "article ii",
                        "article 2", "definition", "term "],
        "redflags":    [],   # all sections
        "query":       [],
    }

    keywords = _INTENT_KEYWORDS.get(intent, [])

    hints: list[str] = []
    for section in structural_map.sections:
        title_lower = section.title.lower()

        # For broad-sweep intents, include all top-level sections
        if intent in {"clause", "redflags"} and section.level <= 1:
            hints.append(section.title)
            continue

        # For targeted intents, match keywords
        if keywords and any(kw in title_lower for kw in keywords):
            hints.append(section.title)

        # Always include sections with matching topic tags
        for tag in section.topic_tags:
            if tag in (_INTENT_TAGS.get(intent, []) + ["penalty", "sla", "payment"]):
                if section.title not in hints:
                    hints.append(section.title)
                break

    # Cap at 40 to avoid context explosion but allow for complex contracts
    return hints[:40]


def _merge_tags(base: list[str], extra: list[str]) -> list[str]:
    """Merge two tag lists, deduplicating while preserving order."""
    seen: set[str] = set()
    merged: list[str] = []
    for t in base + extra:
        if t not in seen:
            seen.add(t)
            merged.append(t)
    return merged


def _fallback_router_system_prompt() -> str:
    return (
        "You are a contract analysis intent router. "
        "Given an intent and optional query, produce a JSON QueryPlan with: "
        "intent, sub_intents, priority_section_tags, chunk_levels, "
        "map_pass_required, max_retrieval_rounds, output_schema_name, analysis_mode."
    )