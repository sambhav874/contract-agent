import asyncio
from app.db.mongodb import MongoDB

async def check_history():
    await MongoDB.connect()
    contract_id = "E2E-BIG-LOGISTICS-20260508-012608"
    kpi_id = "KPI-T1" # Wait, was it uppercase or lowercase in the DB?
    
    # Let's just find all actuals for this contract
    actuals_col = MongoDB.get_collection("actuals")
    actuals = await actuals_col.find({"contract_id": contract_id}).to_list(None)
    print(f"Total actuals for {contract_id}: {len(actuals)}")
    
    # Group by kpi_id
    from collections import defaultdict
    by_kpi = defaultdict(list)
    for a in actuals:
        by_kpi[a["kpi_id"]].append(a)
    
    for kid, items in by_kpi.items():
        print(f"  {kid}: {len(items)} records")
        if kid == "KPI-T1":
            for i in sorted(items, key=lambda x: x.get("timestamp", "")):
                print(f"    - {i.get('timestamp')}: {i.get('value')} {i.get('unit')}")

if __name__ == "__main__":
    asyncio.run(check_history())
