import asyncio
from typing import List, Dict, Any
from app.llm.gemini_client import call_gemini_structured
from app.db.models import EventAnalysisOutput
import os

class EventAgent:
    def __init__(self):
        with open("prompts/event_agent/v1.txt", "r") as f:
            self.prompt_template = f.read()

    async def process_event(self, event_text: str, kpis: List[Dict[str, Any]]) -> EventAnalysisOutput:
        # Format the KPIs for the prompt
        kpi_inventory = "\n".join([f"- {k['kpi_id']}: {k['name']} (Target: {k['operator']} {k['value_min']})" for k in kpis])
        
        full_prompt = f"{self.prompt_template}\n\n## KPI INVENTORY\n{kpi_inventory}\n\n## EVENT TEXT\n{event_text}"
        
        return await call_gemini_structured(full_prompt, EventAnalysisOutput)
