import asyncio
from app.db.mongodb import MongoDB

async def verify_breaches():
    await MongoDB.connect()
    contract_id = "E2E-BIG-LOGISTICS-20260508-012608"
    
    # Check actuals
    actuals_count = await MongoDB.get_collection("actuals").count_documents({"contract_id": contract_id})
    print(f"Actuals count for {contract_id}: {actuals_count}")
    
    # Check breaches
    breaches = await MongoDB.get_collection("breaches").find({"contract_id": contract_id}).to_list(None)
    print(f"Breaches count for {contract_id}: {len(breaches)}")
    
    for b in breaches:
        print(f"  - {b.get('kpi_id')}: is_breach={b.get('is_breach')}, actual={b.get('actual_value')}")

if __name__ == "__main__":
    asyncio.run(verify_breaches())
