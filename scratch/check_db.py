import asyncio
from app.db.mongodb import MongoDB

async def check():
    await MongoDB.connect()
    contracts = await MongoDB.list_contracts()
    print(f"Found {len(contracts)} contracts")
    for c in contracts:
        print(f"- {c.get('contract_id')} ({c.get('name')})")
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
