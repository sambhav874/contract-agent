import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.mongodb import MongoDB

async def run():
    await MongoDB.connect()
    collection = MongoDB.get_collection("actuals")
    actuals = await collection.find({"contract_id": "TEST-AIRPORT-001"}).sort("timestamp", -1).to_list(None)
    
    print(f"Found {len(actuals)} actuals for TEST-AIRPORT-001:")
    for a in actuals:
        print(f"{a['kpi_id']}: {a['value']} {a['unit']} @ {a['timestamp']} (Source: {a.get('source')})")
    
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
