import asyncio
import re
from app.db.mongodb import MongoDB
from app.agents.chat_agent import ChatAgent

async def test():
    await MongoDB.connect()
    agent = ChatAgent(contract_id="prod-logistics-v3")

    question = """Please answer the following approved questions from the contract:
1. [Termination Rights] Under what conditions can theClient terminate the agreement for cause?
2. [Termination Rights] Is there a provision for termination for convenience, and if so, what is the requirednotice period?
3. [Termination Rights] Does the Supplier have the right to terminate the contract if the Client fails to make payments?
11. [Breach & Remediation] Can the contract be terminated immediately upon a breach of any KPI?
12. [Breach & Remediation] What is the processfor curing a breach before termination can be initiated?
13. [Breach & Remediation] Are there specific termination consequences related to the current high breach rate of83.3%?"""

    sub_queries = []
    for line in question.split("\n"):
        line = line.strip()
        match = re.match(r'^\d+\.\s*(?:\[[^\]]+\])?\s*(.*)$', line)
        if match:
            q_text = match.group(1).strip()
            if q_text:
                sub_queries.append(q_text)

    print("Parsed sub-queries:", sub_queries)

    tasks = [
        agent.retriever.fetch(
            contract_id=agent.contract_id,
            query=sq,
            top_k=3,
            levels=None
        ) for sq in sub_queries
    ]
    results = await asyncio.gather(*tasks)

    seen_texts = set()
    chunks = []
    for sub_chunks in results:
        for c in sub_chunks:
            text = c.get("text", "")
            if text not in seen_texts:
                seen_texts.add(text)
                chunks.append(c)

    print(f"\nDeduplicated chunks retrieved: {len(chunks)}")
    for i, c in enumerate(chunks):
        print(f"[{i+1}] Path: {c.get('structural_path')} | Text: {c.get('text', '')[:120]}...")

    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
