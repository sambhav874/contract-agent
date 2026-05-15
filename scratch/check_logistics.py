import asyncio
from app.db.mongodb import MongoDB

async def check():
    await MongoDB.connect()
    contracts = await MongoDB.get_collection("contracts").find({"name": {"$regex": "logistics", "$options": "i"}}).to_list(None)
    if not contracts:
        print("No logistics contract found")
        return
    
    cid = contracts[0]["contract_id"]
    print(f"Contract ID: {cid}")
    
    chunks = await MongoDB.get_collection("chunks").find({"contract_id": cid}).to_list(None)
    print(f"Total Chunks: {len(chunks)}")
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
