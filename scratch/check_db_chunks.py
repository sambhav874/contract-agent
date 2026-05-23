import asyncio
from app.db.mongodb import MongoDB

async def check():
    await MongoDB.connect()
    db = MongoDB.get_collection("chunks")
    cursor = db.find({"contract_id": "prod-logistics-v3"})
    chunks = await cursor.to_list(length=100)
    print(f"Total chunks in DB: {len(chunks)}")
    for i, c in enumerate(chunks):
        print(f"[{i+1}] Path: {c.get('structural_path')} | Text: {c.get('text', '')[:100]}...")
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
