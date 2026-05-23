"""
Intent routing and query planning — LLM-driven, structural-map-aware.

The intent router translates a user intent label + optional free-text query
into a QueryPlan that tells the retrieval layer:
  - which chunk levels to fetch (macro / meso / micro)
  - which section tags to prioritise
  - how many retrieval rounds to allow
  - whether a structural-map pass is required
  - which output schema to target

All routing logic is handled by Gemini Flash.  The only hardcoded fallback
is a static table used when Gemini is unavailable.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.db.models import StructuralMap
from app.llm.gemini_client import call_gemini


# ── Data model ────────────────────────────────────────────────────────────────

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


# ── Valid chunk levels ────────────────────────────────────────────────────────

_VALID_LEVELS = {"macro", "meso", "micro"}

_LEVEL_ALIASES: dict[str, str] = {
    "section": "macro",
    "article": "macro",
    "clause":  "meso",
    "provision": "meso",
    "sentence": "micro",
    "paragraph": "micro",
    "item": "micro",
}

def _normalize_levels(raw: list[str], fallback: list[str]) -> list[str]:
    out = []
    for lvl in raw:
        lvl_lower = lvl.lower()
        if lvl_lower in _VALID_LEVELS:
            out.append(lvl_lower)
        else:
            for alias, canonical in _LEVEL_ALIASES.items():
                if alias in lvl_lower:
                    out.append(canonical)
                    break
    seen: set[str] = set()
    deduped = [x for x in out if not (x in seen or seen.add(x))]  # type: ignore[func-returns-value]
    return deduped or fallback


# ── Static fallback table ─────────────────────────────────────────────────────

_FALLBACK: dict[str, dict[str, Any]] = {
    "CLAUSE_LOOKUP":    {"levels": ["meso"],           "rounds": 3, "schema": "ClauseAnalysisOutput",    "map_pass": True,  "mode": "legal"},
    "SUMMARY":          {"levels": ["macro"],           "rounds": 2, "schema": "SummaryOutput",           "map_pass": True,  "mode": "plain"},
    "OBLIGATION_TRACK": {"levels": ["meso", "micro"],   "rounds": 3, "schema": "ObligationTrackingOutput","map_pass": False, "mode": "plain"},
    "KPI_QUERY":        {"levels": ["micro", "meso"],   "rounds": 4, "schema": "KPIExtractionOutput",     "map_pass": True,  "mode": "plain"},
    "COMPLIANCE":       {"levels": ["meso", "micro"],   "rounds": 3, "schema": "KPIExtractionOutput",     "map_pass": False, "mode": "plain"},
    "RISK_ANALYSIS":    {"levels": ["macro", "meso"],   "rounds": 3, "schema": "RiskAnalysisOutput",      "map_pass": True,  "mode": "legal"},
    "DATA_VIZ":         {"levels": ["micro", "meso"],   "rounds": 3, "schema": "KPIExtractionOutput",     "map_pass": False, "mode": "plain"},
    "DIAGRAM":          {"levels": ["macro", "meso"],   "rounds": 2, "schema": "",                        "map_pass": True,  "mode": "plain"},
    "QA_GENERATE":      {"levels": ["macro"],           "rounds": 2, "schema": "",                        "map_pass": True,  "mode": "plain"},
    "QA_ANSWER":        {"levels": ["meso", "micro"],   "rounds": 4, "schema": "",                        "map_pass": False, "mode": "plain"},
    "CONVERSATIONAL":   {"levels": [],                  "rounds": 0, "schema": "",                        "map_pass": False, "mode": "plain"},
    "GENERAL_QUERY":    {"levels": ["meso"],            "rounds": 3, "schema": "",                        "map_pass": False, "mode": "plain"},
}


# ── Router system prompt ──────────────────────────────────────────────────────

_ROUTER_SYSTEM_PROMPT = """\
You are a query planner for a contract analysis retrieval system.

Given:
  - INTENT: a high-level intent label (see taxonomy below)
  - USER_QUERY: the original user question (may be empty)
  - STRUCTURAL_HINTS: section titles that are structurally relevant (may be empty)
  - CONTRACT_SECTIONS: a compact list of section titles from the contract (may be empty)

Produce a JSON QueryPlan with these fields:
{
  "intent": "<intent label>",
  "sub_intents": ["<optional secondary intents>"],
  "priority_section_tags": ["<section titles or tags to prioritize>"],
  "chunk_levels": ["macro"|"meso"|"micro"],
  "map_pass_required": true|false,
  "max_retrieval_rounds": <int 1-5>,
  "output_schema_name": "<schema name or empty string>",
  "analysis_mode": "plain"|"legal"|"financial"
}

INTENT TAXONOMY:
  CONVERSATIONAL   → no retrieval needed (chunk_levels=[], rounds=0)
  CLAUSE_LOOKUP    → find named section or explain clause text (meso, legal mode)
  SUMMARY          → high-level overview (macro)
  OBLIGATION_TRACK → duties per party (meso+micro)
  KPI_QUERY        → specific KPI details (micro+meso, map_pass=true)
  COMPLIANCE       → breach/penalty status (meso+micro, use DB data)
  DATA_VIZ         → chart/dashboard (micro+meso, use structured data)
  DIAGRAM          → flowchart/structure (macro+meso, map_pass=true)
  QA_GENERATE      → generate questions (macro, map_pass=true)
  QA_ANSWER        → answer specific factual question(s) (meso+micro, rounds=4)
  RISK_ANALYSIS    → red flags / risks (macro+meso, legal mode)
  GENERAL_QUERY    → any other (meso, rounds=3)

RULES:
- priority_section_tags should be specific section titles from CONTRACT_SECTIONS that are relevant.
- For CONVERSATIONAL intent, always return chunk_levels=[] and max_retrieval_rounds=0.
- For KPI-related intents, max_retrieval_rounds should be at least 3.
- Prefer meso+micro for questions requiring exact clause text.
- Prefer macro for high-level structure questions.
- Output ONLY the JSON object, no markdown, no explanation.
"""


# ── Public entry point ────────────────────────────────────────────────────────

async def route_intent(
    intent: str,
    user_query: str | None = None,
    structural_map: StructuralMap | None = None,
) -> QueryPlan:
    """
    Route a user intent to a QueryPlan.

    1. Extracts structural hints from the contract map.
    2. Attempts LLM-driven routing via Gemini Flash.
    3. Falls back to static table if Gemini fails.
    """
    structural_hints = _extract_structural_hints(intent, structural_map)

    try:
        plan = await _route_with_gemini(intent, user_query, structural_map, structural_hints)
        # Always merge structural hints — Gemini may have omitted some
        plan.priority_section_tags = _merge_unique(
            plan.priority_section_tags, structural_hints
        )
        return plan
    except Exception:
        return _route_fallback(intent, structural_hints)


# ── Gemini routing ────────────────────────────────────────────────────────────

async def _route_with_gemini(
    intent: str,
    user_query: str | None,
    structural_map: StructuralMap | None,
    structural_hints: list[str],
) -> QueryPlan:
    section_lines: list[str] = []
    if structural_map:
        for s in structural_map.sections[:80]:
            section_lines.append(
                f"  level={s.level} | id={s.section_id[:20]} | title={s.title[:60]}"
            )

    user_message = (
        f"INTENT: {intent}\n"
        f"USER_QUERY: {user_query or 'N/A'}\n"
        f"STRUCTURAL_HINTS: {structural_hints}\n\n"
        f"CONTRACT_SECTIONS:\n" + ("\n".join(section_lines) if section_lines else "  (none provided)") +
        "\n\nProduce the QueryPlan JSON."
    )

    response = await call_gemini(
        model=settings.gemini_fast_model,
        system_prompt=_ROUTER_SYSTEM_PROMPT,
        user_message=user_message,
        temperature=0.0,
    )

    # call_gemini returns a dict if JSON was parsed, else a string
    if isinstance(response, str):
        cleaned = re.sub(r"```(?:json)?", "", response).strip().rstrip("`").strip()
        import json
        response = json.loads(cleaned)

    raw_levels = response.get("chunk_levels", [])
    fallback_levels = _FALLBACK.get(intent, {}).get("levels", ["meso"])
    levels = _normalize_levels(raw_levels, fallback_levels)

    # KPI intents get at least 3 rounds
    rounds = int(response.get("max_retrieval_rounds", _FALLBACK.get(intent, {}).get("rounds", 3)))
    if intent in ("KPI_QUERY", "COMPLIANCE") and rounds < 3:
        rounds = 3

    return QueryPlan(
        intent=response.get("intent", intent),
        sub_intents=response.get("sub_intents", []),
        priority_section_tags=response.get("priority_section_tags", []),
        chunk_levels=levels,
        map_pass_required=bool(response.get("map_pass_required", False)),
        max_retrieval_rounds=rounds,
        output_schema_name=response.get("output_schema_name", ""),
        analysis_mode=response.get("analysis_mode", "plain"),
    )


# ── Static fallback ───────────────────────────────────────────────────────────

def _route_fallback(intent: str, structural_hints: list[str]) -> QueryPlan:
    cfg = _FALLBACK.get(intent, _FALLBACK["GENERAL_QUERY"])
    return QueryPlan(
        intent=intent,
        sub_intents=[],
        priority_section_tags=structural_hints,
        chunk_levels=cfg["levels"],
        map_pass_required=cfg["map_pass"],
        max_retrieval_rounds=cfg["rounds"],
        output_schema_name=cfg["schema"],
        analysis_mode=cfg["mode"],
    )


# ── Structural hint extraction ────────────────────────────────────────────────

# Intent → keywords that indicate a section is relevant
_INTENT_SECTION_KEYWORDS: dict[str, list[str]] = {
    "RISK_ANALYSIS":    ["indemnif", "liabilit", "terminat", "warrant", "ip ", "force",
                         "dispute", "arbitrat", "penalty", "damages"],
    "KPI_QUERY":        ["kpi", "performance", "sla", "penalty", "payment", "price",
                         "schedule", "target", "milestone", "specification", "standards",
                         "reporting", "audit"],
    "COMPLIANCE":       ["kpi", "performance", "sla", "penalty", "breach", "remedy",
                         "remediation", "cure", "notice of breach"],
    "OBLIGATION_TRACK": ["shall", "must", "obligat", "covenant", "notice", "report",
                         "payment", "terminat"],
    "SUMMARY":          ["recital", "whereas", "article i", "article 1",
                         "definition", "term ", "overview"],
    "DIAGRAM":          ["process", "workflow", "escalation", "procedure", "governance"],
}

# Broad-sweep intents include all top-level sections
_BROAD_INTENTS = {"CLAUSE_LOOKUP", "RISK_ANALYSIS", "QA_GENERATE"}


def _extract_structural_hints(
    intent: str,
    structural_map: StructuralMap | None,
) -> list[str]:
    if not structural_map:
        return []

    keywords = _INTENT_SECTION_KEYWORDS.get(intent, [])
    hints: list[str] = []

    for section in structural_map.sections:
        title_lower = section.title.lower()

        # Broad intents: include all top-level sections
        if intent in _BROAD_INTENTS and section.level <= 1:
            hints.append(section.title)
            continue

        # Targeted intents: match keywords
        if keywords and any(kw in title_lower for kw in keywords):
            if section.title not in hints:
                hints.append(section.title)
            continue

        # Match section topic tags
        relevant_tags = {"penalty", "sla", "payment", "kpi", "performance", "breach"}
        for tag in getattr(section, "topic_tags", []):
            if tag in relevant_tags and section.title not in hints:
                hints.append(section.title)
                break

    return hints[:40]  # cap to avoid context overflow


# ── Utility ───────────────────────────────────────────────────────────────────

def _merge_unique(base: list[str], extra: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in base + extra:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result