import asyncio
from app.db.mongodb import MongoDB
from app.agents.chat_agent import ChatAgent

async def test():
    await MongoDB.connect()
    agent = ChatAgent("FINAL-TEST-001")
    resp = await agent.answer_question("summarize the contract")
    print("\n--- SUMMARY ---")
    print(resp["answer"])
    print("\n--- CITATIONS ---")
    for c in resp["citations"]:
        print(f"- {c['metadata'].get('structural_path')}")
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
