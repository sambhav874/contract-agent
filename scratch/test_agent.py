import asyncio
import os
import sys

# Add app to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.chat_agent import ChatAgent
from app.db.mongodb import MongoDB

async def main():
    await MongoDB.connect()
    agent = ChatAgent(contract_id="prod-logistics-v3")
    print("Agent created.")
    async for chunk in agent.answer_question_stream("What are the payment terms for services rendered under this agreement?"):
        print("CHUNK:", chunk)

if __name__ == "__main__":
    asyncio.run(main())
