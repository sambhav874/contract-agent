import asyncio
import json
import os
import sys

sys.path.append(os.getcwd())
from app.db.mongodb import MongoDB

async def main():
    await MongoDB.connect()
    meta = await MongoDB.get_contract("airport_agreement_2025")
    if meta and "structural_map" in meta:
        sections = meta["structural_map"]["sections"]
        for s in sections:
            print(f"Level {s['level']} | {s['title']}")
    else:
        print("Contract not found")

if __name__ == "__main__":
    asyncio.run(main())
