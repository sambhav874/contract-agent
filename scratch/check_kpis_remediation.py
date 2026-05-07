import asyncio
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app.db.mongodb import MongoDB

async def check_kpis():
    await MongoDB.connect()
    kpis = await MongoDB.get_kpis('airport_agreement_2025')
    
    results = []
    for k in kpis:
        results.append({
            "id": k.get("kpi_id"),
            "name": k.get("name"),
            "remediation": k.get("remediation"),
            "sla": k.get("remediation_sla")
        })
    
    print(json.dumps(results, indent=2))
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check_kpis())
