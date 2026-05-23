import asyncio
from app.agents.chat_agent import classify_intent, ResponseMode

q = "Please answer the following approved questions from the contract:\n1. [Finance] What is the penalty cap?"
mode = classify_intent(q)
print(f"Mode: {mode}")
