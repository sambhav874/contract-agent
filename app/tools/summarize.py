"""Summarize contract tool."""

import json
from app.tools.base import BaseTool, ToolResult
from app.db.mongodb import MongoDB
from app.retrieval.retriever import get_retriever


class SummarizeContractTool(BaseTool):
    name = "summarize_contract"
    description = "Get a high-level summary of the contract: parties, scope, key commercial terms, and major sections."
    input_schema = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.retriever = get_retriever()

    async def _execute(self, **kwargs) -> ToolResult:
        try:
            contract = await MongoDB.get_contract(self.contract_id) or {}
            macro_chunks = await self.retriever.fetch(
                contract_id=self.contract_id,
                query="contract overview parties scope governing law effective date summary",
                levels=["macro"],
                top_k=15,
            )
            summary_text = "\n".join(c.get("text", "")[:1200] for c in macro_chunks[:8])
            data = {
                "name": contract.get("name", "Unknown"),
                "type": contract.get("contract_type", "Unknown"),
                "parties": contract.get("parties", []),
                "effective_date": contract.get("effective_date", "Unknown"),
                "governing_law": contract.get("governing_law", "Unknown"),
                "jurisdiction": contract.get("jurisdiction", "Unknown"),
                "currency": contract.get("currency", ""),
                "overview": summary_text[:4000],
            }
            return ToolResult(success=True, data=data, metadata={"chunks_used": len(macro_chunks)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
