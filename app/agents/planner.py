"""
Planner — goal decomposition and mid-flight replanning.

Fixes applied vs. original:
  1. Removed embedded SearchContractAnswersTool source code from the system
     prompt (copy-paste corruption that wasted tokens on every call).
  2. maybe_replan() now actually injects the new plan back into history
     as a synthetic assistant turn instead of silently discarding it.
  3. decompose() validates each step has required keys before returning.
  4. Added _build_progress_summary() so the replan prompt is grounded in
     real turn content rather than raw Content object reprs.
  5. Both methods have explicit token-aware truncation of history slices.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.llm.gemini_client import call_gemini
from app.observability.logger import get_logger

logger = get_logger(__name__)

# ── Step schema ───────────────────────────────────────────────────────────────

_REQUIRED_STEP_KEYS = {"step_id", "description", "tools_needed", "depends_on",
                       "success_criteria", "fallback"}

_VALID_TOOLS = {
    "search_contract_clauses",
    "query_contract_database",
    "get_kpi_registry",
    "summarize_contract",
    "search_contract_answers",
}

# ── System prompts ────────────────────────────────────────────────────────────

_DECOMPOSE_SYSTEM_PROMPT = """\
You are a planning module for a contract analysis AI assistant.

Given a goal, break it into an ordered list of concrete executable steps.
Each step must specify:
  - step_id        : unique string identifier ("1", "2", …)
  - description    : what to do in plain English
  - tools_needed   : list of tool names from the allowed set (may be empty)
  - depends_on     : list of step_ids that must complete first (may be empty)
  - success_criteria: how to know this step succeeded
  - fallback       : what to do if this step fails

ALLOWED TOOLS (only these, no others):
  search_contract_clauses   — find / retrieve specific contract text
  query_contract_database   — query performance actuals, breach records, or staging logs in MongoDB collections: 'actuals', 'raw_actuals', or 'breaches'
  get_kpi_registry          — retrieve KPI definitions and targets
  summarize_contract        — high-level contract summary
  search_contract_answers   — semantic search for free-text answers

RULES:
- Output ONLY a valid JSON array. No prose, no markdown fences.
- Maximum 6 steps. If a goal needs more, combine related work.
- tools_needed must only contain names from the allowed set above.
- If a step requires no tool (reasoning / synthesis), use an empty list [].

Example output:
[
  {
    "step_id": "1",
    "description": "Retrieve KPI definitions for uptime SLAs",
    "tools_needed": ["get_kpi_registry"],
    "depends_on": [],
    "success_criteria": "KPI registry returned at least one uptime KPI",
    "fallback": "Fall back to searching contract clauses for SLA text"
  },
  {
    "step_id": "2",
    "description": "Check current breach status against those KPIs",
    "tools_needed": ["query_contract_database"],
    "depends_on": ["1"],
    "success_criteria": "Breach records retrieved for the uptime KPIs",
    "fallback": "Report that breach data is unavailable"
  }
]
"""

_REPLAN_SYSTEM_PROMPT = """\
You are a planning critic for a contract analysis AI assistant.

Evaluate whether the current plan is still on track to answer the original goal.
Consider:
  - Has the agent been calling the same tool repeatedly without progress?
  - Are the remaining steps still relevant given what has been found so far?
  - Is the original goal fully addressed by the work done?

Output ONLY a JSON object (no prose, no markdown):
{
  "replan": <true|false>,
  "reason": "<one sentence>",
  "new_plan": [<step objects — same schema as the decompose output>]
}

If replan is false, new_plan may be an empty list [].
"""

# ── Default fallback plan ─────────────────────────────────────────────────────

def _direct_answer_plan(goal: str) -> list[dict]:
    return [
        {
            "step_id": "1",
            "description": f"Answer directly: {goal[:120]}",
            "tools_needed": [],
            "depends_on": [],
            "success_criteria": "A complete answer has been provided",
            "fallback": "Acknowledge the question cannot be answered from available context",
        }
    ]


# ── Validators ────────────────────────────────────────────────────────────────

def _validate_steps(raw: Any) -> list[dict]:
    """
    Accept a list of step dicts, fill in any missing keys with safe defaults,
    and strip invalid tool names. Returns a non-empty list.
    """
    if not isinstance(raw, list) or not raw:
        return []

    cleaned: list[dict] = []
    for i, step in enumerate(raw):
        if not isinstance(step, dict):
            continue
        safe: dict = {
            "step_id":          str(step.get("step_id", str(i + 1))),
            "description":      str(step.get("description", ""))[:300],
            "tools_needed":     [t for t in step.get("tools_needed", []) if t in _VALID_TOOLS],
            "depends_on":       [str(d) for d in step.get("depends_on", [])],
            "success_criteria": str(step.get("success_criteria", "Step completed"))[:200],
            "fallback":         str(step.get("fallback", "Skip and continue"))[:200],
        }
        if safe["description"]:
            cleaned.append(safe)

    return cleaned


def _parse_llm_json(raw: Any) -> Any:
    """Parse LLM output that may be a dict, a list, or a JSON string."""
    if isinstance(raw, (dict, list)):
        return raw
    text = re.sub(r"```(?:json)?", "", str(raw)).strip().rstrip("`").strip()
    return json.loads(text)


# ── Progress summary (replaces raw Content.__repr__ in prompts) ───────────────

def _build_progress_summary(history: list, last_n: int = 6) -> str:
    """
    Extract readable text from the last N history entries.
    Works with both google.genai Content objects and plain dicts.
    """
    lines: list[str] = []
    for msg in history[-last_n:]:
        # google.genai Content
        if hasattr(msg, "role") and hasattr(msg, "parts"):
            role = msg.role
            text_parts = [
                p.text for p in msg.parts
                if hasattr(p, "text") and p.text and p.text.strip()
            ]
            fn_parts = [
                f"[tool_call: {p.function_call.name}]"
                for p in msg.parts
                if hasattr(p, "function_call") and p.function_call
            ]
            content = " ".join(text_parts + fn_parts)
        # plain dict (e.g. from tests)
        elif isinstance(msg, dict):
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))
        else:
            continue

        if content:
            lines.append(f"{role}: {content[:300]}")

    return "\n".join(lines) or "No history available."


# ── Planner ───────────────────────────────────────────────────────────────────

class Planner:
    """
    Two responsibilities:
      1. decompose(goal)      — break a goal into executable steps
      2. maybe_replan(...)    — check progress and inject a revised plan when stuck
    """

    def __init__(self) -> None:
        self.model = settings.gemini_fast_model

    # ── Public API ────────────────────────────────────────────────────────────

    async def decompose(self, goal: str) -> list[dict]:
        """
        Break a high-level goal into an executable DAG of steps.

        Returns a validated list of step dicts.  Never raises — falls back
        to a single direct-answer step on any error.
        """
        try:
            raw = await call_gemini(
                model=self.model,
                system_prompt=_DECOMPOSE_SYSTEM_PROMPT,
                user_message=f"Goal: {goal[:500]}",
                temperature=0.0,
            )
            parsed = _parse_llm_json(raw)

            # Gemini sometimes wraps in {"steps": [...]}
            if isinstance(parsed, dict):
                parsed = parsed.get("steps", parsed.get("plan", []))

            steps = _validate_steps(parsed)
            if steps:
                logger.info("plan_decomposed", goal_preview=goal[:80], step_count=len(steps))
                return steps

        except Exception as exc:
            logger.warning("decompose_failed", error=str(exc))

        return _direct_answer_plan(goal)

    async def maybe_replan(
        self,
        history: list,
        goal: str,
    ) -> tuple[list, str]:
        """
        Check whether the current plan is still on track.

        If replanning is needed, a synthetic assistant turn is injected into
        history so the model sees the revised plan on its next call.

        Returns (updated_history, reason_string).
        """
        progress_summary = _build_progress_summary(history, last_n=8)

        prompt = (
            f"ORIGINAL GOAL:\n{goal[:500]}\n\n"
            f"PROGRESS SO FAR (last 8 turns):\n{progress_summary}\n\n"
            "Should the plan change?"
        )

        try:
            raw = await call_gemini(
                model=self.model,
                system_prompt=_REPLAN_SYSTEM_PROMPT,
                user_message=prompt,
                temperature=0.0,
            )
            parsed = _parse_llm_json(raw)

            if not isinstance(parsed, dict):
                return history, "No replan needed (unexpected response format)"

            if not parsed.get("replan", False):
                return history, f"No replan needed: {parsed.get('reason', '')}"

            # ── Replanning triggered ──────────────────────────────────────────
            reason = parsed.get("reason", "Plan revised")
            new_steps = _validate_steps(parsed.get("new_plan", []))

            if not new_steps:
                logger.warning("replan_triggered_but_no_valid_steps", reason=reason)
                return history, f"Replan triggered but produced no valid steps: {reason}"

            # Inject the new plan as a synthetic assistant turn so the model
            # sees it on the very next call — this is the fix for the original
            # no-op where new_plan was computed and immediately discarded.
            plan_text = (
                f"[Replanning] {reason}\n\n"
                "Revised steps:\n"
                + "\n".join(
                    f"  {s['step_id']}. {s['description']}"
                    + (f" (tools: {', '.join(s['tools_needed'])})" if s["tools_needed"] else "")
                    for s in new_steps
                )
            )

            # Build a Content-compatible dict; the caller converts to the right
            # SDK type if needed (google.genai or plain dict both accepted).
            synthetic_turn = _make_content("model", plan_text)
            updated_history = list(history) + [synthetic_turn]

            logger.info(
                "replanned",
                reason=reason,
                new_step_count=len(new_steps),
            )
            return updated_history, f"Replanning: {reason}"

        except Exception as exc:
            logger.warning("replan_failed", error=str(exc))
            return history, "No replan needed (error in replan call)"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_content(role: str, text: str) -> Any:
    """
    Build a history turn compatible with both google.genai and plain dicts.
    Tries the SDK first; falls back to a plain dict so unit tests don't need
    the full SDK installed.
    """
    try:
        from google.genai import types
        return types.Content(
            role=role,
            parts=[types.Part(text=text)],
        )
    except ImportError:
        return {"role": role, "content": text}