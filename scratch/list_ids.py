
import asyncio
from app.db.mongodb import MongoDB
from app.config import settings

async def list_contracts_and_kpis():
    await MongoDB.connect()
    contracts_col = MongoDB.get_collection("contracts")
    kpis_col = MongoDB.get_collection("kpis")
    
    contracts = await contracts_col.find().to_list(100)
    print(f"Found {len(contracts)} contracts:")
    for c in contracts:
        name = c.get("name", "Unknown")
        cid = c.get("contract_id")
        print(f" - {name} (ID: {cid})")
        
        kpis = await kpis_col.find({"contract_id": cid}).to_list(100)
        for k in kpis:
            print(f"   * KPI: {k.get('name')} (ID: {k.get('kpi_id')})")

if __name__ == "__main__":
    asyncio.run(list_contracts_and_kpis())
