import asyncio
from app.db.mongodb import MongoDB
from app.agents.chat_agent import ChatAgent
import json

async def test_broad_queries():
    await MongoDB.connect()
    contract_id = "FINAL-TEST-001"
    agent = ChatAgent(contract_id)
    
    queries = [
        "summarize the contract",
        "list the kpis from this contract"
    ]
    
    for q in queries:
        print(f"\n--- Testing Query: {q} ---")
        response = await agent.answer_question(q)
        print(f"Answer: {response.get('answer')}")
        print(f"Citations found: {len(response.get('citations', []))}")
        for i, c in enumerate(response.get('citations', [])[:3]):
            print(f"  [{i+1}] {c.get('metadata', {}).get('structural_path', 'N/A')}")
            
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(test_broad_queries())
