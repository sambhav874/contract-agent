# Chat Agent: Agentic AI Review

## Current State: NOT Properly Agentic

The chat agent is a monolithic tool caller with 3 direct DB/retriever tools. It is NOT an orchestrator, does NOT delegate to specialist sub-agents, and has NO contract-level context.

### What's Broken

1. **No Contract Context** — Agent has no idea what contract it is. It only sees KPIs/breaches/actuals.
2. **KPI Tunnel Vision** — `summarize the contract` returns only KPIs. No parties, scope, key terms.
3. **No Sub-Agent Delegation** — SummaryAgent, RiskAgent, ClauseAgent exist in codebase but chat agent never uses them.
4. **No A2A Protocol** — Sub-agents have `analyze()` methods with `query_plan`, `contract_id`, `user_query`. Unused.
5. **Passive Persona** — Says contract "appears to be" a contract. Loses user confidence.
6. **No Reflection** — After tool call, no self-evaluation of whether result is sufficient.
7. **No Long-Term Memory** — Session only, no contract memory.

### What Proper Agentic AI Looks Like

```
ChatOrchestrator (stateful, multi-turn)
├── Contract Context (injected in EVERY prompt)
│   ├── Contract metadata (name, parties, type, date, law)
│   └── Top-level macro chunks (for summary/overview)
├── Intent Router (route_intent from existing codebase)
├── Specialist Sub-Agents (A2A delegation)
│   ├── SummaryAgent → analyze() → SummaryOutput
│   ├── KPIAgent → analyze() → KPIExtractionOutput
│   ├── RiskAgent → analyze() → RiskAnalysisOutput
│   ├── ClauseAgent → analyze() → ClauseAnalysisOutput
│   ├── RedFlagAgent → analyze() → RedFlagOutput
│   └── ObligationAgent → analyze() → ObligationTrackingOutput
├── Tool Layer (ReAct loop)
│   ├── search_contract_clauses (semantic)
│   ├── query_contract_database (MongoDB)
│   ├── get_kpi_registry
│   └── summarize_contract (macro chunk retrieval)
├── Memory
│   ├── Session memory (multi-turn, 2h TTL)
│   └── Contract memory (cached context)
└── Synthesis (streaming to user)
```

### A2A Protocol (Simplified)

```python
class AgentRequest(BaseModel):
    from_agent: str          # "chat_orchestrator"
    to_agent: str            # "summary_agent"
    intent: str              # "summary"
    contract_id: str
    query: str
    context: dict            # shared contract context

class AgentResponse(BaseModel):
    from_agent: str
    status: str             # "success" | "partial" | "error"
    result: dict            # sub-agent output
    citations: list[str]     # chunk_ids / section refs
```

Orchestrator calls sub-agent → gets structured result → synthesizes → streams to user.

### Immediate Fixes Needed

1. **Inject Contract Context** — `_fetch_contract_context()` → metadata + macro chunks, cache on instance, include in every prompt
2. **Add `summarize_contract` Tool** — Fetches macro-level chunks for overview
3. **Delegate to Sub-Agents** — For complex intents (risk, kpi, clause), route to specialist agent
4. **Fix Persona** — "You ARE the Contract Guardian AI for [Contract Name]. Your job is to analyze, explain, and monitor this contract."
5. **Add Reflection Step** — After tool call: "Is this result sufficient? If not, re-query."
6. **Detect Intent Properly** — Use `route_intent()` from existing codebase, not just keyword matching

### Query Behavior Matrix

| User Query | Current | Should Be |
|------------|---------|-----------|
| "What is this?" | "appears to be a contract with KPIs" | "This is the [Name] between [Party A] and [Party B], effective [date], governing law [X]. It covers [scope]. [Brief summary]." |
| "Summarize the contract" | KPI table | Full summary: parties, scope, key terms, KPIs, notable clauses |
| "Find active breaches" | 0 active | "No breaches. Would you like me to run a risk scan?" |
| "Any KPI with penalty?" | JSON dump | "The RSA-129 Decoding Reward has a $100 consequence. Would you like details?" |
| "Explain Article IV" | Generic | Calls ClauseAgent for deep analysis |
| "What are the risks?" | N/A | Delegates to RiskAgent |

### Test Queries (Expected Behavior)

1. "What kind of document is this?" → Contract identity with name, parties, scope
2. "Summarize the contract" → Full summary: parties, scope, key terms, KPIs, conclusions
3. "What does Article IV say?" → Calls search tool, quotes exact text with [Section X.XX] citation
4. "Find active breaches" → Checks breaches collection, reports status, offers next steps
5. "Any KPI with penalty?" → Returns KPI details with penalty info, formatted as prose
6. "What are the risks?" → Delegates to RiskAgent, returns risk analysis

---

## Fix Plan

### Phase 1: Contract Context Injection (fixes identity crisis + summary)
- Add `_fetch_contract_context()` — metadata + macro chunks
- Cache on instance
- Inject into every prompt as `CONTRACT CONTEXT`
- Fix persona: assertive, authoritative

### Phase 2: Sub-Agent Delegation (fixes KPI tunnel vision)
- Map intent → sub-agent
- `summarize` → SummaryAgent
- `kpi` → KPIAgent
- `risk` → RiskAgent
- `clause` → ClauseAgent
- Each delegation: build `AgentRequest`, get `AgentResponse`, synthesize

### Phase 3: A2A Protocol (proper multi-agent)
- Define `AgentRequest` / `AgentResponse` models
- Sub-agents expose `analyze(request: AgentRequest)` interface
- Orchestrator constructs request, calls, gets response

### Phase 4: Reflection & Self-Correction
- After each tool call, evaluate result sufficiency
- If result is empty, re-query with adjusted parameters
- If sub-agent returns low confidence, mention it

### Phase 5: Long-Term Memory
- Cache contract context per contract_id
- Cache sub-agent results for common queries

---

## Implementation

```python
# chat_agent.py — Orchestrator rewrite

class ChatAgent:
    """Orchestrator for contract Q&A. Delegates to sub-agents."""

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.retriever = get_retriever()
        self._contract_context: dict | None = None

    async def _get_contract_context(self) -> dict:
        if self._contract_context is not None:
            return self._contract_context
        contract = await MongoDB.get_contract(self.contract_id)
        # Get key macro chunks for overview
        macro_chunks = await self.retriever.fetch(
            contract_id=self.contract_id,
            query="contract overview parties scope key terms governing law effective date",
            levels=["macro"],
            top_k=10
        )
        self._contract_context = {
            "name": contract.get("name", "Unknown"),
            "type": contract.get("contract_type", "Unknown"),
            "effective_date": contract.get("effective_date", "Unknown"),
            "governing_law": contract.get("governing_law", "Unknown"),
            "jurisdiction": contract.get("jurisdiction", "Unknown"),
            "currency": contract.get("currency", "Unknown"),
            "parties": contract.get("parties", []),
            "macro_summary": "\n".join(c.get("text", "")[:500] for c in macro_chunks[:5]),
        }
        return self._contract_context

    async def answer_question_stream(self, question: str, ...):
        ctx = await self._get_contract_context()
        # Inject contract context into persona
        system = f"""You are the Contract Guardian AI for {ctx['name']}.
        Type: {ctx['type']}
        Parties: {ctx['parties']}
        Effective: {ctx['effective_date']}
        Governing Law: {ctx['governing_law']}
        Jurisdiction: {ctx['jurisdiction']}
        Summary: {ctx['macro_summary'][:2000]}

        {base_persona_rules}"""

        # Route intent
        from app.routing.intent_router import route_intent
        plan = await route_intent(
            intent=detected_intent,  # from classify_intent
            user_query=question,
            structural_map=contract.get("structural_map")  # from contract
        )

        # Delegate to sub-agent based on intent
        if plan.intent == "summary":
            from app.agents.summary_agent import SummaryAgent
            result = await SummaryAgent().analyze(plan, self.contract_id, question)
            yield result.executive_summary  # or similar
        elif plan.intent == "kpi":
            from app.agents.kpi_agent import KPIAgent
            result = await KPIAgent().analyze(plan, self.contract_id, question)
            yield result.model_dump_json()
        # ... other intents
```

---

## Tests

See `test_chat_agent.py` for current tests. After Phase 1:
- Agent knows contract name, parties, type
- Summary returns full contract info, not just KPIs
- Agent sounds authoritative, not uncertain

After Phase 2:
- Delegates to sub-agents for complex queries
- Sub-agent output is synthesized into prose, not dumped as JSON

After Phase 3:
- A2A protocol documented
- Message format standardized
