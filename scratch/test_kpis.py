import asyncio
from app.db.mongodb import MongoDB
from app.agents.chat_agent import ChatAgent

async def test():
    await MongoDB.connect()
    agent = ChatAgent("FINAL-TEST-001")
    resp = await agent.answer_question("list the kpis from this contract")
    print("\n--- KPIs ---")
    print(resp["answer"])
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
