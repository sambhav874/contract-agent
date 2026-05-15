import asyncio
from app.db.mongodb import MongoDB

async def check():
    await MongoDB.connect()
    # Note: contract_id might be different in the DB, let's find it by name or part of ID
    contracts = await MongoDB.get_collection("contracts").find({"name": {"$regex": "airport", "$options": "i"}}).to_list(None)
    if not contracts:
        print("No airport contract found")
        return
    
    cid = contracts[0]["contract_id"]
    print(f"Contract ID: {cid}")
    
    chunks = await MongoDB.get_collection("chunks").find({"contract_id": cid}).to_list(None)
    print(f"Total Chunks: {len(chunks)}")
    
    levels = {}
    for c in chunks:
        l = c.get("chunk_level", "unknown")
        levels[l] = levels.get(l, 0) + 1
    print(f"Levels: {levels}")
    
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
