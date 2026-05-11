"""Chat agent with 3-tier intent classifier and structured data injection."""

from typing import List, Dict, Any, Optional
import json
import os

from app.db.mongodb import MongoDB
from app.llm.gemini_client import call_gemini
from app.retrieval.retriever import get_retriever
from app.agents.ui_guidelines import DATA_VIZ_GUIDELINES, DIAGRAM_GUIDELINES


# ── Intent Classification ─────────────────────────────────────────────

class ResponseMode:
    TEXT_ONLY = "TEXT_ONLY"
    DATA_VIZ = "DATA_VIZ"
    DIAGRAM = "DIAGRAM"


# Keywords / phrases that signal each mode
_DATA_VIZ_SIGNALS = [
    "dashboard", "chart", "graph", "scorecard", "compare", "comparison",
    "target vs actual", "target versus actual", "performance overview",
    "kpi dashboard", "breach dashboard", "penalty breakdown",
    "penalty impact", "trend", "show me the data", "visualize",
    "compliance dashboard", "financial exposure", "penalty waterfall",
    "how are we performing", "performance report", "kpi report",
    "show all kpis", "kpi overview", "breach report",
]

_DIAGRAM_SIGNALS = [
    "flowchart", "diagram", "flow", "process flow", "escalation path",
    "structure", "hierarchy", "architecture", "penalty flow",
    "breach escalation", "remediation flow", "contract structure",
    "decision tree", "workflow",
]

_TEXT_ONLY_SIGNALS = [
    "what is", "what are", "explain", "define", "summarize", "summary",
    "who is", "when is", "where is", "why does", "how does",
    "tell me about", "describe", "list the", "what does",
    "payment terms", "clause", "section", "article",
    "force majeure", "termination", "indemnification",
    "confidentiality", "liability", "warranty",
]


def classify_intent(question: str) -> str:
    """
    Classify the user's question into one of three response modes.

    Priority: TEXT_ONLY > DATA_VIZ > DIAGRAM > fallback TEXT_ONLY

    TEXT_ONLY signals take precedence because a question like
    "explain the penalty clause" should not generate a chart,
    even though "penalty" appears in DATA_VIZ signals.
    
    DIAGRAM is checked before DATA_VIZ because structural keywords
    like "flowchart", "diagram" should override data keywords like "penalty".
    """
    q = question.lower().strip()

    # Check for explicit text-only intent first
    for signal in _TEXT_ONLY_SIGNALS:
        if signal in q:
            # But override if they also explicitly ask for a chart/dashboard/diagram
            has_viz_override = any(v in q for v in ["dashboard", "chart", "graph", "visualize", "show me", "flowchart", "diagram"])
            if not has_viz_override:
                return ResponseMode.TEXT_ONLY

    # Check for diagram intent BEFORE data-viz (diagram keywords are more specific)
    for signal in _DIAGRAM_SIGNALS:
        if signal in q:
            return ResponseMode.DIAGRAM

    # Check for data visualization intent
    for signal in _DATA_VIZ_SIGNALS:
        if signal in q:
            return ResponseMode.DATA_VIZ

    # Default to text-only
    return ResponseMode.TEXT_ONLY


# ── Structured Data Serializer ────────────────────────────────────────

def _serialize_structured_data(
    kpis: List[Dict],
    breaches: List[Dict],
    actuals: List[Dict],
) -> str:
    """
    Build a compact JSON block of real structured data for injection
    into the LLM prompt. This ensures the model has exact values.
    """
    if not kpis and not breaches and not actuals:
        return "\n\nSTRUCTURED DATA: No structured data available for this contract.\n"

    data = {}

    if kpis:
        data["kpis"] = [
            {
                "kpi_id": k.get("kpi_id"),
                "name": k.get("name"),
                "kpi_type": k.get("kpi_type"),
                "value_min": k.get("value_min"),
                "value_max": k.get("value_max"),
                "unit": k.get("unit"),
                "operator": k.get("operator"),
                "party": k.get("party"),
                "consequence_value": k.get("consequence_value"),
                "consequence_unit": k.get("consequence_unit"),
                "remediation": k.get("remediation"),
                "remediation_sla": k.get("remediation_sla"),
                "trigger_condition": k.get("trigger_condition"),
            }
            for k in kpis
        ]

    if breaches:
        data["breaches"] = [
            {
                "kpi_id": b.get("kpi_id"),
                "actual_value": b.get("actual_value"),
                "threshold_value": b.get("threshold_value"),
                "operator": b.get("operator"),
                "is_breach": b.get("is_breach"),
                "penalty_amount": b.get("penalty_amount"),
                "penalty_triggered": b.get("penalty_triggered"),
                "status": b.get("status"),
                "sample_count": b.get("sample_count"),
                "remediation": b.get("remediation"),
                "remediation_sla": b.get("remediation_sla"),
            }
            for b in breaches
        ]

    if actuals:
        # Limit to 50 most recent to avoid context overflow
        sorted_actuals = sorted(
            actuals,
            key=lambda a: a.get("timestamp", ""),
            reverse=True,
        )[:50]
        data["actuals"] = [
            {
                "kpi_id": a.get("kpi_id"),
                "value": a.get("value"),
                "unit": a.get("unit"),
                "timestamp": str(a.get("timestamp", "")),
                "source": a.get("source"),
            }
            for a in sorted_actuals
        ]

    # Summary stats for quick reference
    total_kpis = len(kpis)
    total_breaches = sum(1 for b in breaches if b.get("is_breach"))
    total_penalty = sum(b.get("penalty_amount", 0) for b in breaches if b.get("is_breach"))
    total_actuals = len(actuals)

    data["summary"] = {
        "total_kpis": total_kpis,
        "active_breaches": total_breaches,
        "total_penalty_exposure": round(total_penalty, 2),
        "total_performance_records": total_actuals,
        "breach_rate": f"{(total_breaches / total_kpis * 100):.1f}%" if total_kpis else "0%",
    }

    return f"\n\nSTRUCTURED DATA (use these exact values for any charts/dashboards):\n```json\n{json.dumps(data, indent=2, default=str)}\n```\n"


# ── System Prompts by Mode ────────────────────────────────────────────

_BASE_PERSONA = """You are the Contract Guardian AI, an elite legal and commercial auditor.
Use the provided contract context, breach details, and structured data to answer the user's question accurately.

Rules:
1. CITATIONS: Always cite specific sections or articles using [Section X.XX] format.
2. UNKNOWN: If the information is missing from the context, admit it and suggest where it might normally be found.
3. Be professional, commercially astute, and concise."""

_TEXT_ONLY_PROMPT = f"""{_BASE_PERSONA}

Response format:
- Use clean, well-structured Github Flavored Markdown
- Use tables for comparing 3+ items side by side
- Bold key terms and values
- Quote relevant contract clauses using > blockquotes
- DO NOT generate any HTML, SVG, or code blocks containing visual components
- Keep answers focused and actionable"""

_DATA_VIZ_PROMPT = f"""{_BASE_PERSONA}

You MUST generate a rich, premium visual component for this question.

CRITICAL RULES:
- **NO SLIDERS, NO CALCULATORS, NO SIMULATORS** — the user wants to see actual data, not play with hypothetical values
- Use ONLY values from the STRUCTURED DATA block — never invent numbers
- If structured data is empty or insufficient, explain what data is needed instead of generating a chart
- Wrap the visual in ```html ... ```
- The component must be self-contained (inline styles, Chart.js via CDN)
- Follow the design guidelines below for premium quality

Before the code block, write 1-2 sentences explaining what the visualization shows.
After the code block, write any key insights or observations from the data.

DESIGN GUIDELINES:
{{guidelines}}"""

_DIAGRAM_PROMPT = f"""{_BASE_PERSONA}

You MUST generate a premium SVG diagram for this question.

CRITICAL RULES:
- Use data from the STRUCTURED DATA block where applicable
- The SVG must be self-contained
- Wrap in ```svg ... ```
- Follow the design guidelines below

Before the code block, write 1-2 sentences explaining the diagram.

DESIGN GUIDELINES:
{{guidelines}}"""


# ── Chat Agent ────────────────────────────────────────────────────────

class ChatAgent:
    """Agent for interactive Q&A about contracts and breaches."""

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.retriever = get_retriever()

    async def answer_question(
        self,
        question: str,
        context_breach_id: Optional[str] = None,
        kpis: Optional[List[Dict]] = None,
        breaches: Optional[List[Dict]] = None,
        actuals: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Answer a question about the contract.

        Args:
            question: The user's question
            context_breach_id: Optional breach ID for focused analysis
            kpis: Pre-fetched KPI data (avoids re-fetching if caller has it)
            breaches: Pre-fetched breach data
            actuals: Pre-fetched actuals/performance data
        """

        # 1. Classify intent
        mode = classify_intent(question)

        # 2. If breach context is provided and mode is TEXT_ONLY, it stays text
        #    but if the user is analyzing a breach, upgrade to DATA_VIZ if data exists
        breach_context = ""
        if context_breach_id:
            breaches_coll = MongoDB.get_collection("breaches")
            breach = await breaches_coll.find_one({"breach_id": context_breach_id})
            if breach:
                breach_context = (
                    f"\n\nContext Breach Details:\n"
                    f"- KPI: {breach.get('kpi_id')}\n"
                    f"- Actual: {breach.get('actual_value')}\n"
                    f"- Threshold: {breach.get('threshold_value')}\n"
                    f"- Penalty Triggered: {breach.get('penalty_triggered')}\n"
                    f"- Current Status: {breach.get('status')}"
                )

        # 3. Fetch structured data from MongoDB if not provided
        if kpis is None:
            kpis = await MongoDB.get_kpis(self.contract_id)
            # Clean ObjectIds
            for k in kpis:
                if "_id" in k:
                    k["_id"] = str(k["_id"])
        if breaches is None:
            breaches_list = await MongoDB.get_breaches(self.contract_id)
            for b in breaches_list:
                if "_id" in b:
                    b["_id"] = str(b["_id"])
            breaches = breaches_list
        if actuals is None:
            actuals_list = await MongoDB.get_all_actuals(self.contract_id)
            for a in actuals_list:
                if "_id" in a:
                    a["_id"] = str(a["_id"])
            actuals = actuals_list

        # 4. Build structured data block (only for DATA_VIZ / DIAGRAM)
        structured_data_block = ""
        if mode in (ResponseMode.DATA_VIZ, ResponseMode.DIAGRAM):
            structured_data_block = _serialize_structured_data(kpis, breaches, actuals)
            # If no meaningful data exists, downgrade to TEXT_ONLY
            if not kpis and not breaches and not actuals:
                mode = ResponseMode.TEXT_ONLY

        # 5. Intent-optimized retrieval
        q_lower = question.lower()
        search_kwargs = {"top_k": 15}

        if any(w in q_lower for w in ["summarize", "summary", "overview", "what is this contract about"]):
            search_kwargs["levels"] = ["macro"]
            search_kwargs["top_k"] = 30
        elif any(w in q_lower for w in ["kpi", "performance", "metric", "target", "penalty"]):
            search_kwargs["tags"] = ["kpi", "sla", "penalty", "milestone", "target", "performance"]
            search_kwargs["levels"] = ["meso", "micro"]
            search_kwargs["top_k"] = 25

        # 6. Retrieve relevant contract clauses
        chunks = await self.retriever.fetch(
            contract_id=self.contract_id,
            query=question + breach_context,
            **search_kwargs
        )

        context_text = "\n\n".join(
            [f"[{c.get('structural_path')}] {c.get('text')}" for c in chunks]
        )

        # 7. Build system prompt based on mode
        if mode == ResponseMode.DATA_VIZ:
            system_prompt = _DATA_VIZ_PROMPT.replace("{{guidelines}}", DATA_VIZ_GUIDELINES)
        elif mode == ResponseMode.DIAGRAM:
            system_prompt = _DIAGRAM_PROMPT.replace("{{guidelines}}", DIAGRAM_GUIDELINES)
        else:
            system_prompt = _TEXT_ONLY_PROMPT

        # 8. Call Gemini
        user_message = (
            f"Contract Context:\n{context_text}"
            f"{breach_context}"
            f"{structured_data_block}"
            f"\n\nQuestion: {question}"
        )

        response = await call_gemini(
            model="gemini-3-flash-preview",
            system_prompt=system_prompt,
            user_message=user_message,
        )

        # 9. Extract answer
        answer = ""
        if isinstance(response, dict):
            answer = response.get("answer") or response.get("text") or str(response)
        else:
            answer = str(response)

        return {
            "answer": answer,
            "mode": mode,
            "citations": [
                {
                    "text": c.get("text"),
                    "metadata": {
                        "structural_path": c.get("structural_path"),
                        "chunk_level": c.get("chunk_level"),
                        "chunk_id": c.get("chunk_id"),
                    },
                }
                for c in chunks
            ],
        }
