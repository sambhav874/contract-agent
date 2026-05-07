import asyncio
import json
import os
import sys

# Add current dir to path
sys.path.append(os.getcwd())

from app.db.mongodb import MongoDB

async def main():
    await MongoDB.connect()
    job = await MongoDB.get_latest_job("airport_agreement_2025", "kpi")
    if job and "result" in job:
        print(json.dumps(job["result"]["structured"], indent=2))
    else:
        print("Job not found or no result")

if __name__ == "__main__":
    asyncio.run(main())
