import asyncio
from app.db.mongodb import MongoDB
import json

async def run():
    await MongoDB.connect()
    cid = 'E2E-BIG-LOGISTICS-20260508-012608'
    kpis = await MongoDB.get_kpis(cid)
    c1 = [k for k in kpis if 'c1' in k['kpi_id'].lower()][0]
    c1['_id'] = str(c1['_id'])
    print(json.dumps(c1, indent=2))

if __name__ == "__main__":
    asyncio.run(run())
