"""Search contract clauses tool."""

import json
from app.tools.base import BaseTool, ToolResult
from app.retrieval.retriever import get_retriever


class SearchContractClausesTool(BaseTool):
    name = "search_contract_clauses"
    description = "Search the contract for specific legal clauses, sections, or articles using semantic search. Use for finding wording like 'penalty', 'termination', 'force majeure', or when asked about specific sections."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language query describing what to find."},
            "top_k": {"type": "integer", "description": "Number of chunks to return."},
        },
        "required": ["query"],
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.retriever = get_retriever()

    async def _execute(self, query: str = "", top_k: int = 12) -> ToolResult:
        try:
            chunks = await self.retriever.fetch(
                contract_id=self.contract_id,
                query=query,
                top_k=top_k,
                levels=None,
            )
            data = [{"path": c.get("structural_path"), "text": c.get("text")} for c in chunks]
            return ToolResult(success=True, data=data, metadata={"chunks_found": len(chunks)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
