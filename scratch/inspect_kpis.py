import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.mongodb import MongoDB

async def run():
    await MongoDB.connect()
    kpis = await MongoDB.get_kpis('ROBUST-TEST-002')
    print("KPI Names in ROBUST-TEST-002:")
    for k in kpis:
        print(f"- {k['name']} (ID: {k['kpi_id']})")
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
