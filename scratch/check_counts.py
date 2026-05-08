import asyncio
from app.db.mongodb import MongoDB

async def check():
    await MongoDB.connect()
    contracts = await MongoDB.get_collection('contracts').find().to_list(100)
    for c in contracts:
        cid = c.get('contract_id')
        count = await MongoDB.get_collection('chunks').count_documents({'contract_id': cid})
        print(f"{cid}: {count} chunks")
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
