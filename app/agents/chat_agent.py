from typing import List, Dict, Any, Optional
import os

from app.db.mongodb import MongoDB
from app.llm.gemini_client import call_gemini
from app.retrieval.retriever import get_retriever
from app.agents.ui_guidelines import FULL_GUIDELINES

class ChatAgent:
    """Agent for interactive Q&A about contracts and breaches."""

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.retriever = get_retriever()

    async def answer_question(self, question: str, context_breach_id: Optional[str] = None) -> Dict[str, Any]:
        # 1. Enrich context with breach data if provided
        breach_context = ""
        if context_breach_id:
            breaches_coll = MongoDB.get_collection("breaches")
            breach = await breaches_coll.find_one({"breach_id": context_breach_id})
            if breach:
                breach_context = f"\n\nContext Breach Details:\n- KPI: {breach.get('kpi_id')}\n- Actual: {breach.get('actual_value')}\n- Threshold: {breach.get('threshold_value')}\n- Penalty Triggered: {breach.get('penalty_triggered')}\n- Current Status: {breach.get('status')}"

        # 2. Basic Intent Detection for Retrieval Optimization
        q_lower = question.lower()
        search_kwargs = {"top_k": 15}
        
        # Summarization Intent
        if any(w in q_lower for w in ["summarize", "summary", "overview", "what is this contract about"]):
            search_kwargs["levels"] = ["macro"]
            search_kwargs["top_k"] = 30  # Fetch more for summary
        
        # KPI / Metrics Intent
        elif any(w in q_lower for w in ["kpi", "performance", "metric", "target", "penalty"]):
            search_kwargs["tags"] = ["kpi", "sla", "penalty", "milestone", "target", "performance"]
            search_kwargs["levels"] = ["meso", "micro"]
            search_kwargs["top_k"] = 25

        # 3. Retrieve relevant contract clauses
        # We call the fetch method directly from our native retriever for more control
        chunks = await self.retriever.fetch(
            contract_id=self.contract_id,
            query=question + breach_context,
            **search_kwargs
        )
        
        context_text = "\n\n".join([f"[{c.get('structural_path')}] {c.get('text')}" for c in chunks])

        # 4. Call Gemini via convenience function
        response = await call_gemini(
            model="gemini-3-flash-preview",
            system_prompt=f"""You are the Contract Guardian AI, an elite legal and commercial auditor.
Use the provided contract context and breach details to answer the user's question accurately.

Guidelines:
1. CITATIONS: Always cite specific sections or articles using [Section X.XX] format.
2. BREACHES: If analyzing a breach, focus on 'Excusable Delays', 'Force Majeure', 'Cure Periods', and 'Penalty Tiers'.
3. SUMMARIES: When asked for a summary, provide a high-level executive overview of parties, purpose, term, and key commercial drivers.
4. TABLES: Use Github Flavored Markdown tables ONLY for simple lists or basic data presentation.
5. GENERATIVE UI & DIAGRAMS (ARTIFACTS): You have an advanced rendering engine. If the user asks for a "dashboard", "component", "flowchart", "diagram", or "chart", you MUST generate a rich visual component.
   - **STRICT RULE**: NO SLIDERS, NO CALCULATORS, NO SIMULATORS. The user wants to see actual data, not play with hypothetical values.
   - **Format**: Wrap in ```html ... ``` or ```svg ... ```.
   - **Allowed Tech**: HTML, CSS, JavaScript, SVG, Chart.js.
   - **Guidelines**:
{FULL_GUIDELINES}

6. DATA SOURCE: Never use 'simulated', 'placeholder', or 'dummy' data in charts or components. Use ONLY the specific values, dates, and metrics found in the provided 'Contract Context'. If data for a requested chart is missing, do not generate the chart; instead, report the missing data fields.
7. UNKNOWN: If the information is missing from the context, admit it, but suggest where it might normally be found.

Be professional, commercially astute, and concise.""",
            user_message=f"Contract Context:\n{context_text}\n{breach_context}\n\nQuestion: {question}"
        )

        
        # 5. Extract answer from response
        answer = ""
        if isinstance(response, dict):
            answer = response.get("answer") or response.get("text") or str(response)
        else:
            answer = str(response)

        return {
            "answer": answer,
            "citations": [{"text": c.get("text"), "metadata": {
                "structural_path": c.get("structural_path"),
                "chunk_level": c.get("chunk_level"),
                "chunk_id": c.get("chunk_id")
            }} for c in chunks]
        }
