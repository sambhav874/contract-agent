import asyncio
from app.db.mongodb import MongoDB

async def clear():
    await MongoDB.connect()
    # Delete chunks
    res1 = await MongoDB.get_collection("chunks").delete_many({"contract_id": "airport_food.md"})
    print(f"Deleted {res1.deleted_count} chunks")
    
    # Delete kpis (to be sure)
    res2 = await MongoDB.get_collection("kpis").delete_many({"contract_id": "airport_food.md"})
    print(f"Deleted {res2.deleted_count} kpis")
    
    # Delete contract metadata
    res3 = await MongoDB.get_collection("contracts").delete_many({"contract_id": "airport_food.md"})
    print(f"Deleted {res3.deleted_count} contract records")
    
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(clear())
