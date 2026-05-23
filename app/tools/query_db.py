"""Query contract database tool."""

import json
from typing import Optional
from app.tools.base import BaseTool, ToolResult
from app.db.mongodb import MongoDB


class QueryDatabaseTool(BaseTool):
    name = "query_contract_database"
    description = (
        "Query MongoDB for contract database data. The allowed collection names are exactly: "
        "'actuals' (for performance actuals), 'raw_actuals' (for raw staging logs), or 'breaches' (for breach records). "
        "Do NOT use 'performance_actuals', 'staging_logs', or 'breach_records' under any circumstances."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "collection": {
                "type": "string",
                "enum": ["actuals", "raw_actuals", "breaches"],
                "description": "Target MongoDB collection name. MUST be exactly: 'actuals', 'raw_actuals', or 'breaches'.",
            },
            "filter": {"type": "object", "description": "MongoDB filter dict. Use fields like 'contract_id'."},
            "limit": {"type": "integer", "description": "Max results to return."},
        },
        "required": ["collection"],
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id

    async def _execute(self, collection: str, filter: Optional[dict] = None, limit: int = 20) -> ToolResult:
        try:
            query = filter or {}
            query["contract_id"] = self.contract_id
            coll = MongoDB.get_collection(collection)
            cursor = coll.find(query).limit(limit)
            results = await cursor.to_list(length=limit)
            for r in results:
                if "_id" in r:
                    r["_id"] = str(r["_id"])
            return ToolResult(success=True, data=results, metadata={"count": len(results)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
