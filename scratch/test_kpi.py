import asyncio
import os
import sys
sys.path.append(os.getcwd())
from app.agents.kpi_agent import KPIAgent
from app.routing.intent_router import route_intent
from app.db.mongodb import MongoDB

async def run():
    await MongoDB.connect()
    agent = KPIAgent()
    contract_id = "airport_food.md"
    
    print("Routing intent...")
    query_plan = await route_intent("kpi", structural_map=None)
    
    print(f"Plan: rounds={query_plan.max_retrieval_rounds}, levels={query_plan.chunk_levels}")
    
    print("Running analysis...")
    result = await agent.analyze(
        query_plan=query_plan,
        contract_id=contract_id,
        user_query="Extract all 15 KPIs from Article IV"
    )
    
    print(f"Extracted {len(result.kpis)} KPIs")
    for k in result.kpis:
        print(f" - {k.name} ({k.confidence})")
    
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
