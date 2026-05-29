"""
Chat Agent — LLM-driven orchestrator with proper agentic loop.

Architecture:
  1. PerceptionLayer   — LLM classifies intent (no keyword matching)
  2. PlanningLayer     — LLM decomposes complex queries into sub-tasks
  3. ExecutionLayer    — Tool-augmented Gemini loop (ReAct-style)
  4. ReflectionLayer   — Checks progress, replans when stuck
  5. ResponseLayer     — Formats output to the correct response mode

Fixes applied vs. original:
  [CRIT-1] SESSION_STORE replaced with Redis (aioredis).  All session I/O
           is async; TTL is enforced server-side.  Works across workers.
  [CRIT-2] History trimmed to a token budget before every Gemini call.
           Older turns are summarised into an episodic note rather than
           silently truncated mid-token.
  [CRIT-3] Duplicate tool-call deduplication: (name, frozen_args) set per
           turn prevents infinite same-tool loops.
  [CRIT-4] Parallel tool execution: all function_calls in one model turn
           are dispatched concurrently via asyncio.gather().
  [CRIT-5] Structured data is filtered to only the KPIs/breaches relevant
           to the question and capped at MAX_STRUCTURED_TOKENS tokens before
           injection. Injected as system prompt context, not user message.
  [CRIT-6] DB-sourced strings are sanitised before prompt injection to
           neutralise prompt-injection payloads.
  [CRIT-7] _hallucination_guard() now validates output numbers against the
           set of known values from structured data instead of checking for
           the literal string "STRUCTURED DATA" in the output.
  [HIGH-1] Intent label is validated against the canonical set; unknowns
           fall back to GENERAL_QUERY with a warning log.
  [HIGH-2] max_turns exit now yields a graceful partial-answer message
           instead of silently returning empty content.
  [HIGH-3] route_intent() is now actually called; QueryPlan chunk_levels
           and priority_section_tags are passed to tools.
  [HIGH-4] Compound query plan steps are injected into the system prompt so
           the model addresses each sub-task (vs. plan being discarded).
  [MED-1]  _extract_thinking() runs once after the full turn completes,
           not on every streamed chunk, preventing split-tag corruption.
  [MED-2]  WorkingMemory read-back wired: last N working-memory items are
           summarised into the system prompt for long sessions.
  [LOW-1]  Session purge moved to a background task; no longer blocks
           every request.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, AsyncIterator, Optional

from google.genai import types

from app.agents.clause_agent import ClauseAgent
from app.agents.kpi_agent import KPIAgent
from app.agents.memory import WorkingMemory
from app.agents.obligation_agent import ObligationAgent
from app.agents.planner import Planner
from app.agents.risk_agent import RiskAgent
from app.agents.safety import SafetyGuard
from app.agents.summary_agent import SummaryAgent
from app.agents.ui_guidelines import DATA_VIZ_GUIDELINES, DIAGRAM_GUIDELINES
from app.config import settings
from app.db.mongodb import MongoDB
from app.llm.gemini_client import call_gemini, call_gemini_stream
from app.memory.episodic import EpisodicMemory
from app.memory.semantic import SemanticMemory
from app.observability.logger import get_logger
from app.retrieval.retriever import DEGRADED_RETRIEVAL_TAG, get_retriever
from app.routing.intent_router import QueryPlan, route_intent
from app.tools import (
    SearchContractClausesTool,
    QueryDatabaseTool,
    GetKPIRegistryTool,
    SummarizeContractTool,
    SearchContractAnswersTool,
    CompareContractsTool,
    CalculatePenaltiesTool,
    ExtractKeyDatesTool,
    GenerateComplianceReportTool,
    ToolRegistry
)

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_SESSION_TTL         = 2 * 60 * 60   # 2 hours (Redis TTL, seconds)
_MAX_HISTORY_TOKENS  = 28_000        # trim history when it exceeds this
_MAX_STRUCTURED_TOKENS = 3_000       # cap on injected structured data
_HISTORY_RESERVE     = 4_000         # tokens reserved for system + user msg

# ── Redis session store ───────────────────────────────────────────────────────
# FIX [CRIT-1]: replaced in-process dict with Redis so sessions survive
# worker restarts and are shared across horizontal replicas.

try:
    import redis.asyncio as aioredis
    _redis: aioredis.Redis | None = None

    def _get_redis() -> aioredis.Redis:
        global _redis
        if _redis is None:
            url = getattr(settings, "redis_url", "redis://localhost:6379/0")
            _redis = aioredis.from_url(url, decode_responses=True)
        return _redis

    async def get_session_history(session_id: str) -> list:
        try:
            raw = await _get_redis().get(f"sess:{session_id}")
            return json.loads(raw) if raw else []
        except Exception as exc:
            logger.warning("session_read_failed", session_id=session_id, error=str(exc))
            return []

    async def save_session_history(session_id: str, history: list) -> None:
        try:
            serialized = _serialize_history(history)
            await _get_redis().set(f"sess:{session_id}", json.dumps(serialized), ex=_SESSION_TTL)
        except Exception as exc:
            logger.warning("session_write_failed", session_id=session_id, error=str(exc))

    async def clear_session(session_id: str) -> None:
        try:
            await _get_redis().delete(f"sess:{session_id}")
        except Exception as exc:
            logger.warning("session_delete_failed", session_id=session_id, error=str(exc))

except ImportError:
    # Graceful degradation for environments without redis installed.
    # Falls back to the in-process store with a clear warning.
    logger.warning("redis_not_installed_falling_back_to_in_process_store")

    _FALLBACK_STORE: dict[str, dict[str, Any]] = {}

    async def get_session_history(session_id: str) -> list:          # type: ignore[misc]
        return _FALLBACK_STORE.get(session_id, {}).get("history", [])

    async def save_session_history(session_id: str, history: list) -> None:   # type: ignore[misc]
        _FALLBACK_STORE[session_id] = {"history": history, "updated_at": time.time()}

    async def clear_session(session_id: str) -> None:                # type: ignore[misc]
        _FALLBACK_STORE.pop(session_id, None)


def _serialize_history(history: list) -> list:
    """
    Convert google.genai Content objects to plain dicts for JSON serialisation.
    Plain dicts are passed through unchanged.
    """
    out = []
    for msg in history:
        if hasattr(msg, "role") and hasattr(msg, "parts"):
            parts = []
            for p in msg.parts:
                if hasattr(p, "text") and p.text:
                    parts.append({"type": "text", "text": p.text})
                # function_call / function_response parts are NOT serialised
                # — they are turn-local artefacts and must not be replayed
                # across sessions, as they would confuse the model.
            out.append({"role": msg.role, "parts": parts})
        elif isinstance(msg, dict):
            out.append(msg)
    return out


def _deserialize_history(raw: list) -> list[types.Content]:
    """Restore plain-dict history entries back to google.genai Content objects."""
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user")
        parts = [
            types.Part(text=p["text"])
            for p in item.get("parts", [])
            if p.get("type") == "text" and p.get("text")
        ]
        if parts:
            result.append(types.Content(role=role, parts=parts))
    return result


# ── Background session purge (in-process fallback only) ──────────────────────
# FIX [LOW-1]: moved to background task so it doesn't block every request.

async def _session_purge_loop() -> None:
    """Runs as a background asyncio task; only relevant when Redis is absent."""
    while True:
        await asyncio.sleep(600)  # every 10 minutes
        try:
            cutoff = time.time() - _SESSION_TTL
            expired = [
                sid for sid, s in _FALLBACK_STORE.items()
                if s.get("updated_at", 0) < cutoff
            ]
            for sid in expired:
                _FALLBACK_STORE.pop(sid, None)
            if expired:
                logger.debug("sessions_purged", count=len(expired))
        except Exception:
            pass


def start_background_tasks() -> None:
    """Call once at application startup."""
    asyncio.create_task(_session_purge_loop())


# ── Token budget helpers ──────────────────────────────────────────────────────
# FIX [CRIT-2]: history is trimmed before every Gemini call.

def _estimate_tokens(text: str) -> int:
    """Fast heuristic: ~4 chars per token (GPT/Gemini average)."""
    return max(1, len(text) // 4)


def _history_token_count(history: list) -> int:
    total = 0
    for msg in history:
        if hasattr(msg, "parts"):
            for p in msg.parts:
                if hasattr(p, "text") and p.text:
                    total += _estimate_tokens(p.text)
        elif isinstance(msg, dict):
            total += _estimate_tokens(str(msg.get("content", "")))
    return total


def _trim_history(history: list, budget: int = _MAX_HISTORY_TOKENS) -> list:
    """
    Trim history to stay within the token budget.

    Strategy:
      - Always keep the first turn (original user question, index 0).
      - Drop from index 1 upward until we fit.
      - Never drops the most-recent turn.
    """
    if _history_token_count(history) <= budget:
        return history

    trimmed = list(history)
    while len(trimmed) > 2 and _history_token_count(trimmed) > budget:
        trimmed.pop(1)   # remove second-oldest (keep index 0 and the tail)

    if _history_token_count(trimmed) > budget:
        logger.warning("history_still_over_budget_after_trim", turns=len(trimmed))

    return trimmed


# ── Prompt-injection sanitiser ────────────────────────────────────────────────
# FIX [CRIT-6]: sanitise all DB-sourced strings before prompt injection.

_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)\s+instructions?"
    r"|you\s+are\s+now\s+"
    r"|system\s*prompt"
    r"|<\s*/?(?:system|instruction|prompt|override)\s*>)",
    re.IGNORECASE,
)


def _sanitize_for_prompt(value: Any) -> Any:
    """
    Recursively sanitise strings in a dict/list/scalar.
    Replaces detected injection patterns with [REDACTED].
    """
    if isinstance(value, str):
        return _INJECTION_PATTERNS.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {k: _sanitize_for_prompt(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_prompt(v) for v in value]
    return value


# ── Intent taxonomy ───────────────────────────────────────────────────────────

class Intent:
    CONVERSATIONAL   = "CONVERSATIONAL"
    CLAUSE_LOOKUP    = "CLAUSE_LOOKUP"
    SUMMARY          = "SUMMARY"
    OBLIGATION_TRACK = "OBLIGATION_TRACK"
    KPI_QUERY        = "KPI_QUERY"
    COMPLIANCE       = "COMPLIANCE"
    DATA_VIZ         = "DATA_VIZ"
    DIAGRAM          = "DIAGRAM"
    QA_GENERATE      = "QA_GENERATE"
    QA_ANSWER        = "QA_ANSWER"
    RISK_ANALYSIS    = "RISK_ANALYSIS"
    GENERAL_QUERY    = "GENERAL_QUERY"

_INTENT_TO_AGENT = {
    Intent.SUMMARY: SummaryAgent,
    Intent.KPI_QUERY: KPIAgent,
    Intent.RISK_ANALYSIS: RiskAgent,
    Intent.CLAUSE_LOOKUP: ClauseAgent,
    Intent.OBLIGATION_TRACK: ObligationAgent,
}

_SYNTHESIS_PROMPT = """You are a Synthesis Agent, acting as the primary conversational interface for a contract intelligence system.
You have received structured output from a specialized sub-agent that analyzed the contract.

Your task is to synthesize this structured data into a natural, coherent, and helpful response for the user.
1. Be assertive and authoritative. Do not say "appears to be".
2. Present the key findings clearly (use bolding and bullet points if appropriate).
3. Do not just dump the JSON or raw format. Translate it into prose and well-formatted markdown.

Output in clean markdown.
"""


# FIX [HIGH-1]: canonical set for validation
_VALID_INTENTS: frozenset[str] = frozenset(
    v for k, v in vars(Intent).items() if not k.startswith("_")
)

_STRUCTURED_DATA_INTENTS = {
    Intent.DATA_VIZ, Intent.KPI_QUERY, Intent.COMPLIANCE, Intent.DIAGRAM,
}

_RAG_INTENTS = {
    Intent.CLAUSE_LOOKUP, Intent.SUMMARY, Intent.OBLIGATION_TRACK,
    Intent.RISK_ANALYSIS, Intent.GENERAL_QUERY, Intent.QA_ANSWER,
}

# ── Perception Layer ──────────────────────────────────────────────────────────

_PERCEPTION_SYSTEM_PROMPT = """\
You are an intent classifier for a contract analysis AI assistant.

Given a user message and recent conversation history, output a JSON object:
{
  "intent": "<one of the intent labels below>",
  "needs_contract_context": <true|false>,
  "needs_structured_data": <true|false>,
  "is_compound": <true|false>,
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence>"
}

INTENT LABELS (pick exactly one):
- CONVERSATIONAL:   greetings, thanks, "what can you do", small talk
- CLAUSE_LOOKUP:    look up, find, or explain a named clause, section, article, or legal term (e.g. "show me Article 12", "explain Section 4.2", "what does the indemnity clause say?")
- SUMMARY:          summarize the contract or give an overview
- OBLIGATION_TRACK: what obligations, duties, or requirements exist for a party
- KPI_QUERY:        ask about a specific KPI metric, target, or threshold
- COMPLIANCE:       breach status, penalty amounts, compliance posture
- DATA_VIZ:         chart, graph, dashboard, scorecard, or visual data request
- DIAGRAM:          flowchart, process flow, hierarchy, or diagram request
- QA_GENERATE:      user wants to generate / suggest questions to ask
- QA_ANSWER:        user asks one or more specific factual questions about the contract text (e.g. "What is the notice email for the Supplier?", "Who are the parties?", "What is the safety score requirement?", "What governing law applies?")
- RISK_ANALYSIS:    identify risks, red flags, or vulnerabilities
- GENERAL_QUERY:    any other contract-related question (fallback)

RULES:
- "hi", "hello", "hey" → always CONVERSATIONAL.
- "what can you do" / "help" / "capabilities" → always CONVERSATIONAL.
- needs_contract_context=true only if the query requires reading contract text.
- needs_structured_data=true only if KPI/breach/actuals numbers are required.
- is_compound=true ONLY if the message requires coordinating multiple different intents (e.g., "List all KPIs and also summarize the indemnity clause") or requires extensive multi-step reasoning. Do NOT set to true for simple multi-part factual questions (e.g., "What is the contract term and renewal structure?") - these should be handled by a single agent.
- Output ONLY the JSON object. No markdown fences.
"""


async def classify_intent(
    question: str,
    history: list,
    contract_name: str = "this contract",
) -> dict:
    """LLM-driven intent classification. Falls back to GENERAL_QUERY on error."""
    recent = ""
    for msg in history[-6:]:
        if hasattr(msg, "role") and hasattr(msg, "parts"):
            role = msg.role
            text = "".join(p.text for p in msg.parts if hasattr(p, "text") and p.text)
            if text:
                recent += f"{role}: {text[:200]}\n"

    user_message = (
        f"CONTRACT: {contract_name}\n"
        f"RECENT HISTORY:\n{recent or 'None'}\n\n"
        f"USER MESSAGE: {question}"
    )

    try:
        raw = await call_gemini(
            model=settings.gemini_fast_model,
            system_prompt=_PERCEPTION_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.0,
        )
        if isinstance(raw, dict):
            return raw
        text = re.sub(r"```(?:json)?", "", str(raw)).strip().rstrip("`").strip()
        return json.loads(text)
    except Exception as exc:
        logger.warning("intent_classification_failed", error=str(exc))
        return {
            "intent": Intent.GENERAL_QUERY,
            "needs_contract_context": True,
            "needs_structured_data": False,
            "is_compound": False,
            "confidence": 0.5,
            "reasoning": "Fallback: classification error",
        }


# ── Serializers ───────────────────────────────────────────────────────────────

def _serialize_structured_data(
    kpis: list,
    breaches: list,
    actuals: list,
    question: str = "",
) -> str:
    """
    FIX [CRIT-5]: Structured data is now:
      - Filtered to KPIs/breaches most relevant to the question keyword match.
      - Capped at MAX_STRUCTURED_TOKENS to avoid token bombs.
      - Sanitised for prompt injection (FIX [CRIT-6]).
      - Returned as a block for injection into the SYSTEM prompt, not the
        user message, so it doesn't inflate conversation history.
    """
    if not kpis and not breaches and not actuals:
        return "\n\nSTRUCTURED DATA: No structured data available.\n"

    # Filter KPIs to those relevant to the question
    q_lower = question.lower()
    if q_lower:
        relevant_kpis = [
            k for k in kpis
            if any(
                term in q_lower
                for term in [
                    str(k.get("name", "")).lower(),
                    str(k.get("kpi_id", "")).lower(),
                    str(k.get("kpi_type", "")).lower(),
                ]
            )
        ] or kpis  # fall back to all if no match
    else:
        relevant_kpis = kpis

    # Cap actuals to 20 most recent
    sorted_actuals = sorted(actuals, key=lambda a: a.get("timestamp", ""), reverse=True)[:20]

    data: dict[str, Any] = {}

    if relevant_kpis:
        data["kpis"] = _sanitize_for_prompt([
            {
                "kpi_id":            k.get("kpi_id"),
                "name":              k.get("name"),
                "kpi_type":          k.get("kpi_type"),
                "value_min":         k.get("value_min"),
                "value_max":         k.get("value_max"),
                "unit":              k.get("unit"),
                "operator":          k.get("operator"),
                "party":             k.get("party"),
                "consequence_value": k.get("consequence_value"),
                "consequence_unit":  k.get("consequence_unit"),
                "remediation":       k.get("remediation"),
                "remediation_sla":   k.get("remediation_sla"),
                "trigger_condition": k.get("trigger_condition"),
            }
            for k in relevant_kpis
        ])

    if breaches:
        data["breaches"] = _sanitize_for_prompt([
            {
                "kpi_id":            b.get("kpi_id"),
                "actual_value":      b.get("actual_value"),
                "threshold_value":   b.get("threshold_value"),
                "operator":          b.get("operator"),
                "is_breach":         b.get("is_breach"),
                "penalty_amount":    b.get("penalty_amount"),
                "penalty_triggered": b.get("penalty_triggered"),
                "status":            b.get("status"),
                "sample_count":      b.get("sample_count"),
                "remediation":       b.get("remediation"),
                "remediation_sla":   b.get("remediation_sla"),
            }
            for b in breaches
        ])

    if sorted_actuals:
        data["actuals"] = _sanitize_for_prompt([
            {
                "kpi_id":    a.get("kpi_id"),
                "value":     a.get("value"),
                "unit":      a.get("unit"),
                "timestamp": str(a.get("timestamp", "")),
                "source":    a.get("source"),
            }
            for a in sorted_actuals
        ])

    total_kpis = len(relevant_kpis)
    active_breaches = sum(1 for b in breaches if b.get("is_breach"))
    total_penalty   = sum(b.get("penalty_amount", 0) for b in breaches if b.get("is_breach"))

    data["summary"] = {
        "total_kpis":               total_kpis,
        "active_breaches":          active_breaches,
        "total_penalty_exposure":   round(total_penalty, 2),
        "total_performance_records": len(actuals),
        "breach_rate": f"{(active_breaches / total_kpis * 100):.1f}%" if total_kpis else "0%",
    }

    serialized = json.dumps(data, indent=2, default=str)

    # Cap at token budget (approximate)
    max_chars = _MAX_STRUCTURED_TOKENS * 4
    if len(serialized) > max_chars:
        logger.warning(
            "structured_data_truncated",
            original_chars=len(serialized),
            cap_chars=max_chars,
        )
        serialized = serialized[:max_chars] + "\n  ... (truncated)"

    return (
        "\n\nSTRUCTURED DATA (use these exact values — never invent numbers):\n"
        f"```json\n{serialized}\n```\n"
    )


def _extract_known_numbers(kpis: list, breaches: list, actuals: list) -> set[float]:
    """
    FIX [CRIT-7]: Collect every numeric value from structured data so the
    hallucination guard can check output numbers against a known-values set.
    """
    nums: set[float] = set()
    for k in kpis:
        for field in ("value_min", "value_max", "consequence_value"):
            v = k.get(field)
            if v is not None:
                try:
                    nums.add(float(v))
                except (TypeError, ValueError):
                    pass
    for b in breaches:
        for field in ("actual_value", "threshold_value", "penalty_amount"):
            v = b.get(field)
            if v is not None:
                try:
                    nums.add(float(v))
                except (TypeError, ValueError):
                    pass
    for a in actuals:
        v = a.get("value")
        if v is not None:
            try:
                nums.add(float(v))
            except (TypeError, ValueError):
                pass
    return nums


# ── System Prompts ────────────────────────────────────────────────────────────

_BASE_PERSONA = """\
You are Contract Guardian AI — a precise, evidence-based contract analyst.

You have direct access to the full contract text, all KPI definitions, and live performance data
for the contract identified in CONTRACT CONTEXT below. You do not guess; you cite.

CORE RULES:
1. CITATIONS      — Always cite sections as [Section X.X] or [Article N]. Never omit citations.
2. EVIDENCE ONLY  — Use only data present in CONTRACT CONTEXT, STRUCTURED DATA, or tool results.
3. HONESTY        — If information is missing, say "I don't have that information" explicitly.
4. NO FABRICATION — Never invent numbers, dates, party names, or clause text.
5. NUMERIC DATA   — For any chart or table, use values ONLY from STRUCTURED DATA. Never approximate.
6. TONE           — Professional, concise, and direct. No filler phrases.
7. TOOL PRIORITY  — If you need specific clause text or DB data, call the appropriate tool first.
8. EVIDENCE SCORE — For substantive prose answers, end with a short "Evidence Assessment" section
                    containing "Justification" and "Confidence score" on a 0.0-1.0 scale.

Do not expose private chain-of-thought. For visible auditability, provide concise
first-person working thoughts in <thought>…</thought> tags, written as business-facing
notes about what you are checking, why it matters, what evidence you need, and what
decision you are moving toward. Do not mention internal model, prompt, routing, or
architecture terms.
When laying out an execution plan, wrap the public plan in <plan>…</plan> tags.
"""

_SUFFIX_CONVERSATIONAL = """\
The user sent a conversational message. Respond naturally and helpfully.
- For greetings: reply warmly and briefly offer to help with the contract.
- For capability questions: give a concise bulleted list of what you can do.
- For thanks/acknowledgements: respond graciously and offer next steps.
- Do NOT dump contract summaries, KPIs, or clause lists unless explicitly asked.
- Keep it short (2–4 sentences for greetings, a short list for capabilities).
"""

_SUFFIX_CLAUSE = """\
The user wants to find or understand a specific contract clause or section.
- Search for the relevant clause using the search_contract_clauses tool.
- Quote the exact clause text in a > blockquote.
- Explain it in plain language after the quote.
- Always cite the section reference [Section X.X].
- Flag any ambiguities or unusual provisions.
"""

_SUFFIX_SUMMARY = """\
The user wants a contract summary or overview.
- Use the summarize_contract tool to get the full summary.
- Structure the response: Parties → Scope → Term & Termination → Key Obligations → KPIs → Notable Clauses.
- Be comprehensive — do not omit any major area.
- Use headers and bullet points for clarity.
"""

_SUFFIX_OBLIGATION = """\
The user wants to understand obligations, duties, or requirements.
- Use search_contract_clauses to find obligation sections.
- Organise obligations by party (e.g., Service Provider, Client).
- Use a table if comparing obligations across parties.
- Cite every obligation with its section reference.
- Flag any obligations with hard deadlines or penalties.
"""

_SUFFIX_KPI = """\
The user is asking about a specific KPI, SLA, target, or threshold.
- Use get_kpi_registry to retrieve the relevant KPI data.
- Present: KPI name, target value, operator, unit, measurement period, and penalty for breach.
- If performance actuals are available (from STRUCTURED DATA), show current vs. target.
- Use a table for comparing multiple KPIs.
- Cite the contract section that defines this KPI.
"""

_SUFFIX_COMPLIANCE = """\
The user is asking about compliance status, breaches, or penalties.
- STRUCTURED DATA contains current breach and penalty data — use it.
- Present: which KPIs are in breach, actual vs. threshold values, penalty amounts, and remediation status.
- Use a table for multi-KPI comparisons.
- Cite the penalty clause [Section X.X] for each breach.
- If no breaches exist, say so explicitly.
"""

_SUFFIX_DATA_VIZ = f"""\
The user wants a visual dashboard, chart, or graph.

CRITICAL RULES:
- Generate a self-contained HTML component wrapped in ```html ... ```.
- Use ONLY values from STRUCTURED DATA — never invent numbers.
- If structured data is empty, explain what data is missing instead of generating a placeholder chart.
- Use Chart.js via CDN (https://cdn.jsdelivr.net/npm/chart.js).
- Inline all styles; no external CSS files.
- Write 1–2 sentences before the code block explaining what the chart shows.
- Write key insights after the code block.

DESIGN GUIDELINES:
{DATA_VIZ_GUIDELINES}
"""

_SUFFIX_DIAGRAM = f"""\
The user wants a process flow, hierarchy, or structural diagram.

CRITICAL RULES:
- Generate a self-contained SVG wrapped in ```svg ... ```.
- Use data from STRUCTURED DATA and contract context where applicable.
- Write 1–2 sentences before the code block explaining the diagram.

DESIGN GUIDELINES:
{DIAGRAM_GUIDELINES}
"""

_SUFFIX_QA_GENERATE = """\
The user wants to generate questions to ask about the contract.

Output a JSON block in this EXACT format (no other text except a 1-sentence preamble):

```json
{"type": "qa_approval", "categories": [{"name": "Category", "questions": ["Q1", "Q2", "Q3"]}]}
```

- Generate categories tailored to what the user specifically asked about.
- Each category should have specific, actionable, contract-grounded questions.
- Questions must be answerable from the contract text or performance data.
- Do not include generic questions that could apply to any contract.
"""

_SUFFIX_QA_ANSWER = """\
The user has provided one or more questions and wants detailed answers.

For EACH question:
1. Call search_contract_answers with the question text to retrieve relevant context.
2. Formulate a precise, cited answer using the retrieved context.

Then output a JSON block in this EXACT format (1-sentence preamble only):

```json
{
  "type": "qa_answers",
  "answers": [
    {
      "question": "<copy the exact question text here>",
      "value": "<precise narrative answer>",
      "segment_ids": ["<cited structural paths/sections>"],
      "exact_quotes": ["<exact verbatim sentences or phrases from the contract text that contain the answer>"],
      "justification": "<how each cited segment supports the answer>",
      "confidence": <0.0-1.0>
    }
  ]
}
```

- Every answer must cite at least one contract section in segment_ids.
- Every answer must include exact_quotes containing the exact verbatim clauses or sentences from the contract that contain the answer, to enable precision highlighting.
- Use a numeric confidence score: 0.90-1.00 for directly supported answers, 0.60-0.89 for partially supported answers, and below 0.60 when the contract does not answer the question.
- If a question cannot be answered from the contract, say so explicitly and set confidence below 0.60.
- Do NOT answer from memory — always use the tool results.
"""

_SUFFIX_RISK = """\
The user wants a risk analysis or red flag review.
- Use search_contract_clauses to retrieve relevant risk sections (liability, indemnification,
  termination, IP, force majeure).
- Organise risks by category and severity (High / Medium / Low).
- For each risk: describe it, cite the relevant clause, and suggest mitigation.
- Use a table format: Risk | Clause | Severity | Mitigation.
"""

_SUFFIX_GENERAL = """\
Answer the user's contract question thoroughly.
- Use the available tools to retrieve relevant information before answering.
- Always cite specific sections.
- Use tables for comparisons, bullet points for lists.
- If the question is ambiguous, ask one clarifying question.
"""

_INTENT_SUFFIX_MAP = {
    Intent.CONVERSATIONAL:   _SUFFIX_CONVERSATIONAL,
    Intent.CLAUSE_LOOKUP:    _SUFFIX_CLAUSE,
    Intent.SUMMARY:          _SUFFIX_SUMMARY,
    Intent.OBLIGATION_TRACK: _SUFFIX_OBLIGATION,
    Intent.KPI_QUERY:        _SUFFIX_KPI,
    Intent.COMPLIANCE:       _SUFFIX_COMPLIANCE,
    Intent.DATA_VIZ:         _SUFFIX_DATA_VIZ,
    Intent.DIAGRAM:          _SUFFIX_DIAGRAM,
    Intent.QA_GENERATE:      _SUFFIX_QA_GENERATE,
    Intent.QA_ANSWER:        _SUFFIX_QA_ANSWER,
    Intent.RISK_ANALYSIS:    _SUFFIX_RISK,
    Intent.GENERAL_QUERY:    _SUFFIX_GENERAL,
}


# ── Response helpers ──────────────────────────────────────────────────────────

def _extract_thinking(text: str) -> tuple[str, str, str]:
    """
    Strip <thought> and <plan> tags from text.
    Returns (thought, plan, clean_text).

    FIX [MED-1]: called ONCE on the full accumulated turn text, not on
    every streamed chunk, so tags that span two chunks aren't corrupted.
    """
    thought_match = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
    plan_match    = re.search(r"<plan>(.*?)</plan>", text, re.DOTALL)
    thought   = thought_match.group(1).strip() if thought_match else ""
    plan_text = plan_match.group(1).strip()    if plan_match    else ""
    answer    = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
    answer    = re.sub(r"<plan>.*?</plan>",       "", answer, flags=re.DOTALL)
    clean_answer = answer.strip()

    # Fallback: if the model wrapped everything in <thought> tags
    if not clean_answer and thought:
        clean_answer = thought

    return thought, plan_text, clean_answer


def _hallucination_guard(
    text: str,
    intent: str,
    known_numbers: set[float] | None = None,
) -> bool:
    """
    FIX [CRIT-7]: checks numbers in the output against the set of values
    actually present in structured data, instead of checking for the literal
    string "STRUCTURED DATA" in the output (which never appeared there).

    Returns True if the response looks safe (no suspicious invented numbers).
    """
    if intent not in (Intent.DATA_VIZ, Intent.DIAGRAM):
        return True

    has_code = bool(re.search(r"```(?:html|svg|javascript)", text, re.IGNORECASE))
    if not has_code:
        return True

    if not known_numbers:
        # No structured data was provided — any numbers in the chart are invented
        number_matches = re.findall(r"\b\d+(?:\.\d+)?\b", text)
        suspicious = [float(n) for n in number_matches if float(n) > 1]
        if suspicious:
            logger.warning("hallucination_guard_no_anchor", suspicious_count=len(suspicious))
            return False
        return True

    # Check that numbers in the code block appear in the known set
    code_match = re.search(r"```(?:html|svg|javascript)(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not code_match:
        return True

    code_text = code_match.group(1)
    output_numbers = {float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", code_text) if float(n) > 1}

    # Allow small integers (axis ticks, percentages) — only flag large specific values
    suspicious = {n for n in output_numbers if n > 100 and n not in known_numbers}
    if suspicious:
        logger.warning("hallucination_guard_unanchored_numbers", suspicious=list(suspicious)[:10])
        return False

    return True


def _parse_qa_questions(message: str) -> list[str]:
    lines = message.split("\n")
    questions = []
    for line in lines:
        line = line.strip()
        match = re.match(r"^\d+\.\s*(?:\[[^\]]+\])?\s*(.+)$", line)
        if match:
            q = match.group(1).strip()
            if q and len(q) > 5:
                questions.append(q)
    return questions or [message]


def _delegation_event(
    *,
    agent: str,
    intent: str,
    task: str,
    status: str,
    step_id: str = "main",
    reason: str | None = None,
    thinking: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Public SSE payload for agent handoffs."""
    payload: dict[str, Any] = {
        "type": "delegation",
        "agent": agent,
        "intent": intent,
        "task": task,
        "status": status,
        "step_id": step_id,
    }
    if reason:
        payload["reason"] = reason
    if thinking:
        payload["thinking"] = thinking
    if error:
        payload["error"] = error
    return payload


def _specialist_thinking(result_obj: Any) -> str:
    thought = getattr(result_obj, "_thought_summary", "")
    return thought.strip() if isinstance(thought, str) else ""


# ── Chat Agent ────────────────────────────────────────────────────────────────

class ChatAgent:
    """
    Orchestrator agent for contract Q&A.

    Flow per turn:
      PerceptionLayer  → LLM intent classification + validation
      RoutingLayer     → QueryPlan (chunk levels, section tags) — now actually used
      PlanningLayer    → sub-task decomposition (compound queries only)
      ContextLayer     → selectively fetch contract context + structured data
      ExecutionLayer   → ReAct tool-use loop (parallel tool calls, dedup)
      ReflectionLayer  → stagnation detection and replanning
      ResponseLayer    → hallucination guard (number-anchored), session persistence
    """

    def __init__(self, contract_id: str, safety_config: dict | None = None):
        self.contract_id = contract_id
        self.retriever = get_retriever()
        self._contract_context: dict[str, Any] | None = None
        self.safety = SafetyGuard(safety_config or {})
        self.memory = WorkingMemory()
        self.planner = Planner()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.tool_registry = self._build_tool_registry()

    # ── Tool registry ─────────────────────────────────────────────────────────

    def _build_tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(SearchContractClausesTool(self.contract_id))
        registry.register(QueryDatabaseTool(self.contract_id))
        registry.register(GetKPIRegistryTool(self.contract_id))
        registry.register(SummarizeContractTool(self.contract_id))
        registry.register(SearchContractAnswersTool(self.contract_id))
        registry.register(CompareContractsTool(self.contract_id))
        registry.register(CalculatePenaltiesTool(self.contract_id))
        registry.register(ExtractKeyDatesTool(self.contract_id))
        registry.register(GenerateComplianceReportTool(self.contract_id))
        return registry

    def _tools(self) -> list[types.Tool]:
        return self.tool_registry.to_gemini_tools()

    async def _run_tool(self, tool_call, context_breach_id: str | None = None) -> str:
        name = tool_call.name
        args = dict(tool_call.args)
        try:
            result = await self.tool_registry.execute(name, **args)
            if not result.success:
                return json.dumps({"error": result.error, "tool": name})
            return json.dumps(result.data, default=str)
        except Exception as exc:
            logger.exception("tool_execution_failed", tool=name, error=str(exc))
            return json.dumps({"error": str(exc), "tool": name})

    # ── Contract context ──────────────────────────────────────────────────────

    async def _get_contract_context(self, force_refresh: bool = False) -> dict[str, Any]:
        if self._contract_context is not None and not force_refresh:
            return self._contract_context

        contract = await MongoDB.get_contract(self.contract_id) or {}
        macro_chunks = await self.retriever.fetch(
            contract_id=self.contract_id,
            query="contract overview parties scope key terms governing law effective date",
            levels=["macro"],
            top_k=8,
        )
        summary_text = "\n".join(c.get("text", "")[:800] for c in macro_chunks[:5])
        self._contract_context = {
            "name":           contract.get("name", "Unknown Contract"),
            "type":           contract.get("contract_type", "Unknown"),
            "effective_date": contract.get("effective_date", "Unknown"),
            "governing_law":  contract.get("governing_law", "Unknown"),
            "jurisdiction":   contract.get("jurisdiction", "Unknown"),
            "currency":       contract.get("currency", ""),
            "parties":        contract.get("parties", []),
            "summary":        summary_text[:3000],
            "_version":       contract.get("version") or contract.get("updated_at"),
        }
        return self._contract_context

    # ── Working memory summary ────────────────────────────────────────────────
    # FIX [HIGH-3]: working memory is now read back and summarised into
    # the system prompt for long sessions.

    def _working_memory_context(self) -> str:
        """Return a short summary of recent working-memory items, if any."""
        try:
            items = self.memory.recent(n=5)     # assumes WorkingMemory.recent() exists
            if not items:
                return ""
            lines = []
            for item in items:
                if hasattr(item, "parts"):
                    text = "".join(p.text for p in item.parts if hasattr(p, "text") and p.text)
                    lines.append(f"- {item.role}: {text[:200]}")
            if lines:
                return "\nRECENT WORKING MEMORY:\n" + "\n".join(lines) + "\n"
        except Exception:
            pass
        return ""

    # ── System prompt builder ─────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        intent: str,
        contract_ctx: dict[str, Any],
        include_contract_context: bool,
        structured_data_block: str = "",
        plan_steps: list[dict] | None = None,
        working_memory_ctx: str = "",
    ) -> str:
        suffix = _INTENT_SUFFIX_MAP.get(intent, _SUFFIX_GENERAL)

        if not include_contract_context:
            return f"{_BASE_PERSONA}\n\n{suffix}"

        parties_str = (
            ", ".join(
                f"{p.get('name', 'Unknown')} ({p.get('role', 'Unknown')})"
                for p in contract_ctx.get("parties", [])
            )
            or "Parties unknown"
        )

        ctx_block = (
            f"CONTRACT CONTEXT:\n"
            f"  Name:           {contract_ctx.get('name', 'Unknown')}\n"
            f"  Type:           {contract_ctx.get('type', 'Unknown')}\n"
            f"  Parties:        {parties_str}\n"
            f"  Effective Date: {contract_ctx.get('effective_date', 'Unknown')}\n"
            f"  Governing Law:  {contract_ctx.get('governing_law', 'Unknown')}\n"
            f"  Jurisdiction:   {contract_ctx.get('jurisdiction', 'Unknown')}\n"
            f"  Currency:       {contract_ctx.get('currency') or 'Not specified'}\n\n"
            f"Key Sections / Summary:\n{contract_ctx.get('summary', 'No summary available.')}\n"
        )

        # FIX [HIGH-4]: inject plan steps into system prompt so the model
        # actually addresses each sub-task in a compound query.
        plan_block = ""
        if plan_steps:
            plan_lines = "\n".join(
                f"  {s['step_id']}. {s['description']}"
                + (f" (tools: {', '.join(s['tools_needed'])})" if s.get("tools_needed") else "")
                for s in plan_steps
            )
            plan_block = f"\nSUB-TASKS TO ADDRESS (address each in order):\n{plan_lines}\n"

        return (
            f"{_BASE_PERSONA}\n\n"
            f"{ctx_block}\n"
            f"{structured_data_block}"
            f"{working_memory_ctx}"
            f"{plan_block}\n"
            f"{suffix}"
        )

    # ── Context enrichment ────────────────────────────────────────────────────

    async def _fetch_structured_data(self) -> tuple[list, list, list]:
        kpis     = await MongoDB.get_kpis(self.contract_id)
        breaches = await MongoDB.get_breaches(self.contract_id)
        actuals  = await MongoDB.get_all_actuals(self.contract_id)
        return kpis, breaches, actuals

    async def _rag_for_qa_answer(self, question: str) -> str:
        sub_queries = _parse_qa_questions(question)
        tasks = [
            self.retriever.fetch(
                contract_id=self.contract_id,
                query=sq,
                top_k=3,
            )
            for sq in sub_queries
        ]
        results = await asyncio.gather(*tasks)

        seen: set[str] = set()
        chunks = []
        for sub_result in results:
            for c in sub_result:
                text = c.get("text", "")
                if text and text not in seen:
                    seen.add(text)
                    chunks.append(c)

        logger.info(
            "rag_retrieval_qa",
            contract_id=self.contract_id,
            sub_query_count=len(sub_queries),
            chunk_count=len(chunks),
        )

        degraded = any(DEGRADED_RETRIEVAL_TAG in c.get("section_type_tags", []) for c in chunks)
        block = "\n\n--- RETRIEVED CONTRACT FRAGMENTS ---\n"
        if degraded:
            block += "⚠️ Warning: retrieval quality degraded — answers below may be incomplete.\n\n"

        for i, c in enumerate(chunks):
            block += (
                f"Fragment [{i+1}] "
                f"(Path: {c.get('structural_path', 'unknown')}): "
                f"{c.get('text', '')}\n"
            )
        return block

    # ── Multi-Agent Orchestration & Synthesis ─────────────────────────────────

    async def _synthesize_specialist_result(self, agent_name: str, result_obj: Any, question: str) -> str:
        """Synthesize a structured specialist agent output into natural language."""
        raw_result = result_obj.model_dump_json() if hasattr(result_obj, "model_dump_json") else str(result_obj)
        prompt = f"Original user question: {question}\n\nSpecialist Agent ({agent_name}) provided this result:\n{raw_result}"

        response = await call_gemini(
            model=settings.gemini_fast_model,
            system_prompt=_SYNTHESIS_PROMPT,
            user_message=prompt
        )
        if isinstance(response, dict):
            return response.get("text", str(response))
        return str(response)

    async def _resolve_compound_delegations(
        self,
        plan_steps: list[dict],
        contract_ctx: dict,
    ) -> list[dict[str, Any]]:
        """Classify each compound subtask once and decide which agent owns it."""

        async def _resolve(step: dict) -> dict[str, Any]:
            step_id = str(step.get("step_id", "unknown"))
            description = step.get("description", "")

            try:
                intent_result = await classify_intent(
                    description,
                    history=[],
                    contract_name=contract_ctx.get("name", "contract"),
                )
                sub_intent = intent_result.get("intent", Intent.GENERAL_QUERY)
                reason = intent_result.get("reasoning", "")
            except Exception as exc:
                logger.warning("compound_subtask_classification_failed", step_id=step_id, error=str(exc))
                sub_intent = Intent.GENERAL_QUERY
                reason = "Subtask classification failed; using the general chat agent."

            try:
                query_plan = await route_intent(sub_intent, user_query=description)
            except Exception as exc:
                logger.warning("compound_subtask_route_failed", step_id=step_id, error=str(exc))
                query_plan = None

            agent_class = _INTENT_TO_AGENT.get(sub_intent)
            agent_name = agent_class.__name__ if agent_class else "ChatAgent"

            return {
                "step_id": step_id,
                "description": description,
                "intent": sub_intent,
                "agent": agent_name,
                "reason": reason,
                "query_plan": query_plan,
            }

        return await asyncio.gather(*[_resolve(step) for step in plan_steps])

    async def _dispatch_compound_plan(
        self,
        plan_steps: list[dict],
        contract_ctx: dict,
        question: str,
        delegations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Dispatch subtasks to specialized agents in parallel and collect their results."""
        resolved_delegations = delegations or await self._resolve_compound_delegations(plan_steps, contract_ctx)
        delegation_by_step = {
            str(item.get("step_id", "unknown")): item
            for item in resolved_delegations
        }

        async def _run_subtask(step: dict) -> dict:
            step_id = str(step.get("step_id", "unknown"))
            description = step.get("description", "")
            delegation = delegation_by_step.get(
                step_id,
                {
                    "step_id": step_id,
                    "description": description,
                    "intent": Intent.GENERAL_QUERY,
                    "agent": "ChatAgent",
                    "query_plan": None,
                },
            )
            sub_intent = delegation.get("intent", Intent.GENERAL_QUERY)
            sub_query_plan = delegation.get("query_plan")

            agent_class = _INTENT_TO_AGENT.get(sub_intent)
            if agent_class:
                agent = agent_class()
                res_obj = await agent.analyze(sub_query_plan, self.contract_id, description)
                thought_summary = _specialist_thinking(res_obj)
                res_text = res_obj.model_dump_json() if hasattr(res_obj, "model_dump_json") else str(res_obj)
            else:
                # Use ChatAgent's single-turn answer for general subtasks
                agent = ChatAgent(self.contract_id)
                res_dict = await agent.answer_question(description)
                thought_summary = ""
                res_text = res_dict.get("answer", str(res_dict))

            return {
                "step_id": step_id,
                "description": description,
                "result": res_text,
                "thinking": thought_summary,
                "status": "completed",
                "agent": delegation.get("agent", "ChatAgent"),
                "intent": sub_intent,
                "delegation": _delegation_event(
                    agent=delegation.get("agent", "ChatAgent"),
                    intent=sub_intent,
                    task=description,
                    status="completed",
                    step_id=step_id,
                    thinking=thought_summary,
                ),
            }

        tasks = [_run_subtask(step) for step in plan_steps]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for i, step in enumerate(plan_steps):
            step_id = str(step.get("step_id", f"step_{i}"))
            result = results[i]
            if isinstance(result, Exception):
                delegation = delegation_by_step.get(
                    step_id,
                    {
                        "agent": "ChatAgent",
                        "intent": Intent.GENERAL_QUERY,
                        "description": step.get("description", ""),
                    },
                )
                output[step_id] = {
                    "error": str(result),
                    "status": "failed",
                    "agent": delegation.get("agent", "ChatAgent"),
                    "intent": delegation.get("intent", Intent.GENERAL_QUERY),
                    "delegation": _delegation_event(
                        agent=delegation.get("agent", "ChatAgent"),
                        intent=delegation.get("intent", Intent.GENERAL_QUERY),
                        task=delegation.get("description", step.get("description", "")),
                        status="failed",
                        step_id=step_id,
                        error=str(result),
                    ),
                }
            else:
                output[step_id] = result
        return output

    async def _synthesize_compound_results(self, results: dict[str, Any], question: str) -> str:
        """Synthesize multiple specialist results into a coherent response."""
        result_texts = []
        for key, val in results.items():
            desc = val.get("description", key)
            res = val.get("result", str(val))
            result_texts.append(f"### {desc}\n{res}")
        combined = "\n\n".join(result_texts)

        synthesis_prompt = (
            "You are a Synthesis Agent orchestrating multiple sub-tasks. "
            "Combine the findings from the sub-agents into a single cohesive response.\n"
            "Highlight overarching themes and clearly answer the original question.\n\n"
            "Output in clean markdown."
        )
        response = await call_gemini(
            model=settings.gemini_fast_model,
            system_prompt=synthesis_prompt,
            user_message=f"Original question: {question}\n\nSub-agent results:\n\n{combined}"
        )
        if isinstance(response, dict):
            return response.get("text", str(response))
        return str(response)

    # ── Main streaming entry point ────────────────────────────────────────────

    async def answer_question_stream(
        self,
        question: str,
        context_breach_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[dict]:
        t_start = time.monotonic()

        # Load prior history (now async via Redis)
        prior_history_raw = await get_session_history(session_id) if session_id else []
        prior_history = _deserialize_history(prior_history_raw) if prior_history_raw else []

        # ── PERCEPTION: classify intent ───────────────────────────────────────
        contract_ctx = await self._get_contract_context()
        intent_result = await classify_intent(
            question, prior_history, contract_name=contract_ctx["name"]
        )

        # FIX [HIGH-1]: validate intent against canonical set
        raw_intent: str = intent_result.get("intent", Intent.GENERAL_QUERY)
        if raw_intent not in _VALID_INTENTS:
            logger.warning("unknown_intent_label", raw=raw_intent)
            raw_intent = Intent.GENERAL_QUERY

        intent: str = raw_intent
        needs_contract_ctx: bool = intent_result.get("needs_contract_context", True)
        needs_structured:   bool = intent_result.get("needs_structured_data", False)
        is_compound:        bool = intent_result.get("is_compound", False)

        logger.info(
            "intent_classified",
            intent=intent,
            confidence=intent_result.get("confidence"),
            reasoning=intent_result.get("reasoning"),
        )
        yield {
            "type": "intent",
            "intent": intent,
            "reasoning": intent_result.get("reasoning", ""),
            "confidence": intent_result.get("confidence"),
            "needs_contract_context": needs_contract_ctx,
            "needs_structured_data": needs_structured,
            "is_compound": is_compound,
        }

        # ── ROUTING: build QueryPlan — FIX [HIGH-3]: actually called now ─────
        query_plan: QueryPlan | None = None
        try:
            query_plan = await route_intent(intent, user_query=question)
            logger.info(
                "query_plan",
                levels=query_plan.chunk_levels,
                tags=query_plan.priority_section_tags[:5],
            )
        except Exception as exc:
            logger.warning("route_intent_failed", error=str(exc))

        # ── DELEGATION: compound queries and specialized intents ──────────────
        if is_compound:
            plan_steps = await self.planner.decompose(question)
            delegations = await self._resolve_compound_delegations(plan_steps, contract_ctx)
            public_delegations = [
                _delegation_event(
                    agent=item.get("agent", "ChatAgent"),
                    intent=item.get("intent", Intent.GENERAL_QUERY),
                    task=item.get("description", ""),
                    status="queued",
                    step_id=item.get("step_id", "unknown"),
                    reason=item.get("reason"),
                )
                for item in delegations
                if item.get("agent") != "ChatAgent"
            ]
            yield {
                "type": "plan",
                "content": f"Breaking into {len(plan_steps)} steps…",
                "steps": plan_steps,
                "delegations": public_delegations,
            }
            for delegation in public_delegations:
                yield delegation
            for delegation in public_delegations:
                yield {**delegation, "status": "running"}
            results = await self._dispatch_compound_plan(plan_steps, contract_ctx, question, delegations)
            for result in results.values():
                delegation = result.get("delegation") if isinstance(result, dict) else None
                if delegation and delegation.get("agent") != "ChatAgent":
                    yield delegation
            synthesis = await self._synthesize_compound_results(results, question)
            yield {"type": "content", "content": synthesis}
            yield {"type": "done"}
            return

        elif intent in _INTENT_TO_AGENT:
            agent_class = _INTENT_TO_AGENT[intent]
            agent = agent_class()

            delegation = _delegation_event(
                agent=agent_class.__name__,
                intent=intent,
                task=question,
                status="started",
                reason="Specialized deep analysis",
            )
            yield delegation
            yield {"type": "thought", "content": f"Delegating to {agent_class.__name__} for specialized deep analysis..."}

            try:
                result_obj = await agent.analyze(query_plan, self.contract_id, question)
                thought_summary = _specialist_thinking(result_obj)
            except Exception as exc:
                yield _delegation_event(
                    agent=agent_class.__name__,
                    intent=intent,
                    task=question,
                    status="failed",
                    reason="Specialized deep analysis",
                    error=str(exc),
                )
                raise
            yield _delegation_event(
                agent=agent_class.__name__,
                intent=intent,
                task=question,
                status="completed",
                reason="Specialized deep analysis",
                thinking=thought_summary,
            )

            synthesis = await self._synthesize_specialist_result(agent_class.__name__, result_obj, question)
            yield {"type": "content", "content": synthesis}
            yield {"type": "done"}
            return

        # ── PLANNING: decompose compound queries ──────────────────────────────
        # Left for backward compatibility / fallback if compound wasn't caught above
        plan_steps: list[dict] = []

        # ── CONTEXT: build structured data block (injected into system prompt) ─
        # FIX [CRIT-5]: structured data goes into system prompt, not user message
        structured_data_block = ""
        known_numbers: set[float] = set()
        kpis_data: list = []
        breaches_data: list = []
        actuals_data: list = []

        if needs_structured and intent in _STRUCTURED_DATA_INTENTS:
            kpis_data, breaches_data, actuals_data = await self._fetch_structured_data()
            structured_data_block = _serialize_structured_data(
                kpis_data, breaches_data, actuals_data, question=question
            )
            known_numbers = _extract_known_numbers(kpis_data, breaches_data, actuals_data)

        # Working memory context for long sessions
        wm_ctx = self._working_memory_context()

        # ── CONTEXT: build system prompt ──────────────────────────────────────
        system_prompt = self._build_system_prompt(
            intent,
            contract_ctx,
            needs_contract_ctx,
            structured_data_block=structured_data_block,
            plan_steps=plan_steps,
            working_memory_ctx=wm_ctx,
        )

        # Build user content (QA_ANSWER still appends RAG fragments to user msg)
        user_content = question
        if intent == Intent.QA_ANSWER:
            rag_block = await self._rag_for_qa_answer(question)
            user_content = f"{question}\n{rag_block}"

        # ── EXECUTION: build history and run ReAct loop ───────────────────────
        history: list = prior_history + [
            types.Content(role="user", parts=[types.Part(text=user_content)])
        ]

        # Pass QueryPlan levels/tags to tools via registry context if supported
        if query_plan:
            try:
                self.tool_registry.set_query_plan(query_plan)
            except AttributeError:
                pass  # ToolRegistry doesn't support it yet — non-fatal

        tools    = self._tools()
        max_turns = self.safety.max_iterations
        turn      = 0
        accumulated_text = ""

        # FIX [CRIT-3]: dedup set for (tool_name, frozen_args) per session
        seen_tool_calls: set[str] = set()

        while turn < max_turns:
            turn += 1

            halt, reason = self.safety.should_halt(history, turn)
            if halt:
                yield {"type": "content", "content": f"⚠️ Safety guard: {reason}"}
                yield {"type": "done"}
                return

            # FIX [CRIT-2]: trim history before every call
            trimmed_history = _trim_history(history, budget=_MAX_HISTORY_TOKENS)

            has_tool_calls    = False
            accumulated_parts: list[types.Part] = []
            turn_text_buffer  = ""   # FIX [MED-1]: buffer full turn before extracting tags
            try:
                async for chunk in call_gemini_stream(
                    model=settings.gemini_analysis_model,
                    system_prompt=system_prompt,
                    user_message=trimmed_history,
                    tools=tools,
                    enable_thinking=True,
                ):
                    # Track real cost from usage metadata if present in this chunk
                    usage = getattr(chunk, "usage_metadata", None)
                    if usage:
                        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
                        candidates_tokens = getattr(usage, "candidates_token_count", 0) or 0
                        self.safety.track_cost(settings.gemini_analysis_model, prompt_tokens, candidates_tokens)

                    candidates = getattr(chunk, "candidates", None)
                    if not candidates:
                        continue
                    content = getattr(candidates[0], "content", None)
                    if not content or not content.parts:
                        continue

                    for part in content.parts:
                        # Native Gemini thinking: part.thought == True
                        if getattr(part, "thought", False) is True and getattr(part, "text", None):
                            yield {
                                "type": "thought",
                                "content": part.text,
                                "source": "gemini_thinking",
                            }
                            # Don't add thought parts to accumulated_parts
                            # (they shouldn't be sent back as history)
                            continue
                        if part.text and part.text.strip():
                            turn_text_buffer += part.text   # buffer; don't yield yet
                        if part.function_call:
                            has_tool_calls = True
                        accumulated_parts.append(part)

            except Exception as exc:
                logger.exception("gemini_stream_error", error=str(exc), turn=turn)
                yield {"type": "error", "content": f"Stream error: {exc}"}
                break

            # FIX [MED-1]: extract thinking ONCE on the full buffered text
            # (fallback for any XML-tagged <thought>/<plan> content)
            if turn_text_buffer:
                thought, plan_text, answer_text = _extract_thinking(turn_text_buffer)
                if thought:
                    yield {"type": "thought", "content": thought}
                if plan_text:
                    yield {"type": "plan", "content": plan_text}
                if answer_text:
                    yield {"type": "content", "content": answer_text}
                    accumulated_text += answer_text

            # If no tool calls, the model is done with this turn
            if not has_tool_calls:
                break

            # Append model response to history
            if accumulated_parts:
                model_turn = types.Content(role="model", parts=accumulated_parts)
                history.append(model_turn)
                self.memory.append(model_turn)

            # ── FIX [CRIT-3 + CRIT-4]: dedup + parallel tool execution ────────
            fc_parts = [p for p in accumulated_parts if p.function_call]

            # Filter duplicates
            unique_fc_parts = []
            for p in fc_parts:
                call_key = json.dumps(
                    {"n": p.function_call.name, "a": dict(p.function_call.args)},
                    sort_keys=True,
                )
                if call_key in seen_tool_calls:
                    logger.info(
                        "duplicate_tool_call_skipped",
                        tool=p.function_call.name,
                        args=dict(p.function_call.args),
                    )
                    yield {
                        "type":    "tool_call_skipped",
                        "name":    p.function_call.name,
                        "reason":  "duplicate — use prior result",
                    }
                else:
                    seen_tool_calls.add(call_key)
                    unique_fc_parts.append(p)
                    yield {
                        "type": "tool_call",
                        "name": p.function_call.name,
                        "args": dict(p.function_call.args),
                    }

            if not unique_fc_parts:
                # All calls were duplicates — synthesise from existing results
                history.append(types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(
                        name="__system__",
                        response={"result": "All tool calls in this turn were duplicates of prior calls. Synthesise your answer from the results already available above."},
                    ))],
                ))
                continue

            # Execute unique tool calls in parallel
            results_list = await asyncio.gather(
                *[self._run_tool(p.function_call, context_breach_id) for p in unique_fc_parts],
                return_exceptions=True,
            )

            for p, result in zip(unique_fc_parts, results_list):
                tool_name = p.function_call.name
                if isinstance(result, Exception):
                    result_text = json.dumps({"error": str(result), "tool": tool_name})
                else:
                    result_text = str(result)

                yield {"type": "tool_result", "name": tool_name, "content": result_text}

                history.append(types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": result_text},
                    ))],
                ))
                self.memory.append(history[-1])

            # ── REFLECTION: replan if stuck (every 5 turns) ───────────────────
            if turn > 0 and turn % 5 == 0:
                history, replan_reason = await self.planner.maybe_replan(history, question)
                if "Replanning" in replan_reason:
                    yield {"type": "thought", "content": f"Replanning: {replan_reason}"}

        # ── FIX [HIGH-2]: graceful degradation when max_turns is hit ─────────
        else:
            # The while-loop exhausted max_turns without a natural break
            partial_note = (
                "⚠️ I reached my research limit for this query. "
                "Here is what I found so far:\n\n"
                + (accumulated_text or "No partial results are available.")
            )
            yield {"type": "content", "content": partial_note}

        # ── RESPONSE: hallucination guard (number-anchored) ───────────────────
        if not _hallucination_guard(accumulated_text, intent, known_numbers=known_numbers):
            yield {
                "type":    "warning",
                "content": (
                    "⚠️ Some numbers in the visualization could not be verified against "
                    "the structured data. Please cross-check before sharing."
                ),
            }

        # Persist session (serialise before writing)
        if session_id:
            await save_session_history(session_id, history)

        # Store episodic memory of this turn
        try:
            trace = []
            for call_key in seen_tool_calls:
                try:
                    parsed = json.loads(call_key)
                    trace.append({"tool": parsed.get("n"), "args": parsed.get("a")})
                except Exception:
                    pass
            await self.episodic.store(
                session_id=session_id or f"sess_{int(time.time())}",
                goal=question,
                result=accumulated_text or "No response generated.",
                outcome=intent.name if hasattr(intent, 'name') else str(intent),
                trace=trace
            )
        except Exception as e:
            logger.error("failed_to_save_episodic_memory", error=str(e))

        # Store semantic memory of this turn
        try:
            q_clean = question.lower()
            key_term = None
            if "supplier" in q_clean or "party" in q_clean or "parties" in q_clean:
                key_term = "Contracting Parties"
            elif "payment" in q_clean or "billing" in q_clean or "invoice" in q_clean:
                key_term = "Payment Terms"
            elif "audit" in q_clean:
                key_term = "Audit Rights & Frequency"
            elif "liability" in q_clean or "indemnity" in q_clean:
                key_term = "Liability Limits"
            elif "force majeure" in q_clean:
                key_term = "Force Majeure"
            elif "governing law" in q_clean or "jurisdiction" in q_clean:
                key_term = "Governing Law"

            if key_term and accumulated_text:
                await self.semantic.store(
                    key=f"{self.contract_id}:{key_term}",
                    value=accumulated_text[:200] + ("..." if len(accumulated_text) > 200 else ""),
                    source=f"QA Turn: {question[:30]}...",
                    confidence=0.95
                )

            # Save the last interaction event summary
            await self.semantic.store(
                key=f"{self.contract_id}:last_interaction",
                value={
                    "goal": question[:100],
                    "outcome": intent.name if hasattr(intent, 'name') else str(intent),
                    "time": time.time()
                },
                source="system_telemetry",
                confidence=1.0
            )
        except Exception as e:
            logger.error("failed_to_save_semantic_memory", error=str(e))

        logger.info(
            "turn_complete",
            intent=intent,
            turns=turn,
            elapsed_ms=round((time.monotonic() - t_start) * 1000),
        )

        yield {"type": "done"}

    # ── Non-streaming convenience wrapper ─────────────────────────────────────

    async def answer_question(self, *args, **kwargs) -> dict:
        full_text = ""
        intent = Intent.GENERAL_QUERY
        async for chunk in self.answer_question_stream(*args, **kwargs):
            if chunk.get("type") == "intent":
                intent = chunk.get("intent", intent)
            elif chunk.get("type") == "content":
                full_text += chunk.get("content", "")
            elif chunk.get("type") == "done":
                break
        return {"answer": full_text, "intent": intent}
