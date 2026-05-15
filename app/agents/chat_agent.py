"""Chat agent with 3-tier intent classifier and structured data injection."""

from typing import List, Dict, Any, Optional
import json
import os
import time

from app.db.mongodb import MongoDB
from app.llm.gemini_client import call_gemini, call_gemini_stream
from app.retrieval.retriever import get_retriever
from app.agents.ui_guidelines import DATA_VIZ_GUIDELINES, DIAGRAM_GUIDELINES
from google.genai import types
from app.config import settings


# ── Session History Store ──────────────────────────────────────────────
# Keyed by session_id → { "history": list[types.Content], "updated_at": float }
# This keeps multi-turn conversation context alive across HTTP requests.
_SESSION_STORE: Dict[str, Dict[str, Any]] = {}
_SESSION_TTL_SECONDS = 2 * 60 * 60  # 2 hours


def _purge_expired_sessions() -> None:
    """Remove sessions that haven't been used in TTL window."""
    cutoff = time.time() - _SESSION_TTL_SECONDS
    expired = [sid for sid, s in _SESSION_STORE.items() if s["updated_at"] < cutoff]
    for sid in expired:
        del _SESSION_STORE[sid]


def get_session_history(session_id: str) -> list:
    """Return the stored Gemini history list for a session (empty list if new)."""
    _purge_expired_sessions()
    return _SESSION_STORE.get(session_id, {}).get("history", [])


def save_session_history(session_id: str, history: list) -> None:
    """Persist updated Gemini history for a session."""
    _SESSION_STORE[session_id] = {"history": history, "updated_at": time.time()}


def clear_session(session_id: str) -> None:
    """Wipe a session's history (e.g. when user starts a new conversation)."""
    _SESSION_STORE.pop(session_id, None)


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
    **kwargs
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

    raw_actuals = kwargs.get("raw_actuals", [])
    if raw_actuals:
        data["raw_actuals_staging"] = [
            {
                "raw_id": r.get("raw_id"),
                "source": r.get("source"),
                "data": r.get("data"),
                "status": r.get("status"),
                "ingested_at": str(r.get("ingested_at", ""))
            }
            for r in raw_actuals[:20]
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
Use the tools at your disposal to fetch contract text and performance data.

Thinking Process:
1.  **Analyze**: Understand the user's intent.
2.  **Plan**: Determine which tools are needed (clauses, performance data, raw logs).
3.  **Execute**: Call tools.
4.  **Synthesize**: Combine evidence into a final answer.

Rules:
1. CITATIONS: Always cite specific sections or articles using [Section X.XX] format.
2. EVIDENCE: Never invent data. Only use what is returned from tools.
3. ADMIT: If data is missing after querying, admit it.

CRITICAL: When thinking or planning, use <thought> and <plan> XML tags. DO NOT wrap these tags inside markdown code blocks (e.g. do NOT use ```xml). Output the tags directly in plain text.
"""


_TEXT_ONLY_PROMPT = f"""{_BASE_PERSONA}

Response format:
- Use clean, well-structured Github Flavored Markdown
- Use tables for comparing 3+ items side by side
- Bold key terms and values
- Quote relevant contract clauses using > blockquotes
"""

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
    """Agent for interactive Q&A about contracts and breaches using dynamic tools."""

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.retriever = get_retriever()

    def _get_tool_definitions(self) -> list[types.Tool]:
        """Define the tools available to the agent."""
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="search_contract_clauses",
                        description="Search for specific legal clauses or sections in the contract using semantic search.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "query": types.Schema(type="STRING", description="The search query (e.g. 'Force Majeure', 'Late Payment Penalty')"),
                                "top_k": types.Schema(type="INTEGER", description="Number of chunks to return (default 10)"),
                            },
                            required=["query"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="query_contract_database",
                        description="Query performance actuals, raw staging logs, or breach records from MongoDB.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "collection": types.Schema(
                                    type="STRING", 
                                    enum=["actuals", "raw_actuals", "breaches"],
                                    description="The collection to query"
                                ),
                                "filter": types.Schema(
                                    type="OBJECT", 
                                    description="MongoDB filter (e.g. {'kpi_id': 'KPI-1'})"
                                ),
                                "limit": types.Schema(type="INTEGER", description="Limit results (default 20)")
                            },
                            required=["collection"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="get_kpi_registry",
                        description="Get the full list of KPIs, their targets, operators, and associated penalties.",
                        parameters=types.Schema(type="OBJECT", properties={})
                    )
                ]
            )
        ]

    async def _execute_tool(self, tool_call: Any) -> str:
        """Execute a tool call and return the result as a string."""
        name = tool_call.name
        args = tool_call.args
        
        try:
            if name == "search_contract_clauses":
                chunks = await self.retriever.fetch(
                    contract_id=self.contract_id,
                    query=args.get("query"),
                    top_k=args.get("top_k", 10)
                )
                return json.dumps([{
                    "path": c.get("structural_path"),
                    "text": c.get("text")
                } for c in chunks])

            elif name == "query_contract_database":
                coll_name = args.get("collection")
                query_filter = args.get("filter", {})
                limit = args.get("limit", 20)
                
                # Security: Force contract_id
                query_filter["contract_id"] = self.contract_id
                
                coll = MongoDB.get_collection(coll_name)
                cursor = coll.find(query_filter).limit(limit)
                results = await cursor.to_list(length=limit)
                
                for r in results:
                    if "_id" in r: r["_id"] = str(r["_id"])
                
                return json.dumps(results, default=str)

            elif name == "get_kpi_registry":
                kpis = await MongoDB.get_kpis(self.contract_id)
                for k in kpis:
                    if "_id" in k: k["_id"] = str(k["_id"])
                return json.dumps(kpis, default=str)
                
            return f"Error: Tool {name} not found."
        except Exception as e:
            return f"Error executing tool {name}: {str(e)}"

    async def answer_question_stream(
        self,
        question: str,
        context_breach_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        Streaming version of answer_question that yields thoughts, tool calls, and results.
        Supports multi-turn conversation via `session_id`.
        """
        # 1. Setup
        mode = classify_intent(question)

        # ── Rehydrate prior conversation history ──────────────────────
        # Prior turns are stored as serialised Gemini Content objects.
        # We load them, append the new user message, and save back after
        # each agentic turn so the NEXT call sees the full conversation.
        prior_history: list = get_session_history(session_id) if session_id else []

        history = prior_history + [
            types.Content(role="user", parts=[types.Part(text=f"Question: {question}")])
        ]
        
        system_prompt = _TEXT_ONLY_PROMPT
        if mode == ResponseMode.DATA_VIZ:
            system_prompt = _DATA_VIZ_PROMPT.replace("{{guidelines}}", DATA_VIZ_GUIDELINES)
        elif mode == ResponseMode.DIAGRAM:
            system_prompt = _DIAGRAM_PROMPT.replace("{{guidelines}}", DIAGRAM_GUIDELINES)

        tools = self._get_tool_definitions()
        
        # 2. Main Agent Loop
        max_turns = 15
        turn = 0
        

        print(f"DEBUG: Starting answer_question_stream for: {question}")
        while turn < max_turns:
            turn += 1
            print(f"DEBUG: turn {turn}")
            
            has_tool_calls = False

            # ── Accumulate the full response turn before processing ──────────
            # This is critical for Gemini thinking models (gemini-2.5-*).
            # These models attach a `thought_signature` to each Part that
            # contains a function_call. If we reconstruct the Part from scratch
            # (e.g. types.Part(function_call=fc)), the signature is lost and the
            # next API call raises 400 INVALID_ARGUMENT.
            #
            # Strategy:
            #   • Stream text chunks → yield to client in real-time (low latency)
            #   • Collect ALL parts from every chunk into `accumulated_parts`
            #   • After the stream ends, build ONE model Content from those parts
            #     and append it to history (preserving thought_signatures).
            #   • Then execute tool calls and append function_response turns.

            accumulated_parts: list = []  # raw Part objects from the SDK

            try:
                async for chunk in call_gemini_stream(
                    model="gemini-2.0-flash",
                    system_prompt=system_prompt,
                    user_message=history,
                    tools=tools
                ):
                    if not (chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts):
                        continue

                    for part in chunk.candidates[0].content.parts:
                        # Stream text to client in real-time
                        if part.text and part.text.strip():
                            print(f"DEBUG: raw_text_chunk: {repr(part.text)}")
                            yield {"type": "content", "content": part.text}

                        # Announce tool calls to client in real-time
                        if part.function_call:
                            has_tool_calls = True
                            fc = part.function_call
                            print(f"DEBUG: tool_call: {fc.name}")
                            yield {"type": "tool_call", "name": fc.name, "args": fc.args}

                        # Always accumulate the original part (preserves thought_signature)
                        accumulated_parts.append(part)

            except Exception as e:
                print(f"DEBUG: Gemini stream error: {e}")
                yield {"type": "content", "content": f"Error communicating with AI: {str(e)}"}
                break

            if not has_tool_calls:
                # Pure text turn — we're done
                print("DEBUG: No tool calls this turn, stopping.")
                break

            # ── Append the complete model turn (with thought_signatures) ─────
            if accumulated_parts:
                history.append(types.Content(role="model", parts=accumulated_parts))

            # ── Execute each tool call and append results ────────────────────
            for part in accumulated_parts:
                if not part.function_call:
                    continue
                fc = part.function_call
                result = await self._execute_tool(fc)
                print(f"DEBUG: tool_result: {fc.name} (length: {len(result)})")
                yield {"type": "tool_result", "name": fc.name, "content": result}

                history.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name,
                                response={"result": result}
                            )
                        )]
                    )
                )
            
        print("DEBUG: Agent loop finished.")

        # ── Persist history for next turn ────────────────────────────────────
        # Strip the new user message (which is already in prior_history as far
        # as the NEXT call is concerned — we save the FULL updated history so
        # the model sees everything that happened in this turn).
        if session_id:
            save_session_history(session_id, history)

        yield {"type": "done"}


    async def answer_question(self, *args, **kwargs) -> Dict[str, Any]:
        """Legacy non-streaming wrapper (optional, for backward compatibility)."""
        # For now, just collect the stream and return the final content
        full_text = ""
        mode = "TEXT_ONLY"
        async for chunk in self.answer_question_stream(*args, **kwargs):
            if chunk["type"] == "content":
                full_text += chunk["content"]
        return {"answer": full_text, "mode": mode}
