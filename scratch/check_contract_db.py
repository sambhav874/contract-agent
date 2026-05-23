import asyncio
from app.db.mongodb import MongoDB

async def main():
    await MongoDB.connect()
    contracts = await MongoDB.list_contracts()
    print("Contracts:")
    for c in contracts:
        print(c.get("contract_id"))
    
    chunks = MongoDB.get_collection("chunks")
    saas_chunks = await chunks.count_documents({"contract_id": "saas_agreement_2025"})
    print(f"Chunks for saas_agreement_2025: {saas_chunks}")
    
    airport_chunks = await chunks.count_documents({"contract_id": "airport_agreement_2025"})
    print(f"Chunks for airport_agreement_2025: {airport_chunks}")

asyncio.run(main())
