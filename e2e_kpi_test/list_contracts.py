import asyncio
from app.db.mongodb import MongoDB

async def list_contracts():
    await MongoDB.connect()
    contracts = await MongoDB.get_collection("contracts").find().to_list(None)
    for c in sorted(contracts, key=lambda x: x.get("created_at", ""), reverse=True):
        print(f"- {c.get('contract_id')} ({c.get('name', 'N/A')})")

if __name__ == "__main__":
    asyncio.run(list_contracts())
