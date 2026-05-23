import asyncio
import json
import os
from app.db.mongodb import MongoDB
from app.agents.chat_agent import ChatAgent

async def test():
    await MongoDB.connect()

    # Use a real contract ID you have ingested
    agent = ChatAgent(contract_id="contract_1747492193")

    q = "Please answer the following approved questions from the contract:\n1. [Finance] What is the penalty cap?"

    print("Starting stream...")
    async for chunk in agent.answer_question_stream(q, session_id="test1234"):
        print("CHUNK:", chunk)

    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
