"""Search contract answers tool."""

import json
from app.tools.base import BaseTool, ToolResult
from app.retrieval.retriever import get_retriever


class SearchContractAnswersTool(BaseTool):
    name = "search_contract_answers"
    description = "Search the contract specifically to answer a generated question."
    input_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The specific question to answer."},
        },
        "required": ["question"],
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.retriever = get_retriever()

    async def _execute(self, question: str = "", **kwargs) -> ToolResult:
        try:
            chunks = await self.retriever.fetch(
                contract_id=self.contract_id,
                query=question,
                top_k=15,
                levels=None,
            )
            data = [{"path": c.get("structural_path"), "text": c.get("text")} for c in chunks]
            return ToolResult(success=True, data=data, metadata={"chunks_found": len(chunks)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
