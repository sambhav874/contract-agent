import asyncio
import os
import sys
import json
from bson import ObjectId

# Add project root to path
sys.path.append(os.getcwd())

from app.db.mongodb import MongoDB

def json_serial(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError ("Type %s not serializable" % type(obj))

async def get_kpi_detail():
    await MongoDB.connect()
    kpis = await MongoDB.get_kpis('airport_agreement_2025')
    kpi = next((k for k in kpis if k['kpi_id'] == 'kpi_009'), None)
    if kpi:
        print(json.dumps(kpi, indent=2, default=json_serial))
    else:
        print("KPI not found")
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(get_kpi_detail())
