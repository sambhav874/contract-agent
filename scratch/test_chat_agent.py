import asyncio
from app.agents.chat_agent import ChatAgent

async def test():
    agent = ChatAgent(contract_id="contract_abc")
    q = "Please answer the following approved questions from the contract:\n1. [Finance] What is the penalty cap?"

    # We want to see if it calls a tool
    async for chunk in agent.answer_question_stream(q, session_id="test1234"):
        print(chunk)

asyncio.run(test())
