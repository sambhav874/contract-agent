import asyncio
from app.db.mongodb import MongoDB

async def debug():
    await MongoDB.connect()
    cid = 'E2E-BIG-LOGISTICS-20260508-012608'
    kpis = await MongoDB.get_kpis(cid)
    actuals = await MongoDB.get_latest_actuals(cid)
    print(f"KPIS ({len(kpis)}): {[k['kpi_id'] for k in kpis]}")
    print(f"ACTUALS ({len(actuals)}): {[a['kpi_id'] for a in actuals]}")

if __name__ == "__main__":
    asyncio.run(debug())
