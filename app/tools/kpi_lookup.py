"""KPI registry tool."""

import json
from app.tools.base import BaseTool, ToolResult
from app.db.mongodb import MongoDB


class GetKPIRegistryTool(BaseTool):
    name = "get_kpi_registry"
    description = "Get all KPIs, targets, operators, penalties, remediations, and responsible parties. Use for KPI lookup."
    input_schema = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id

    async def _execute(self, **kwargs) -> ToolResult:
        try:
            kpis = await MongoDB.get_kpis(self.contract_id)
            for k in kpis:
                if "_id" in k:
                    k["_id"] = str(k["_id"])
            return ToolResult(success=True, data=kpis, metadata={"count": len(kpis)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
