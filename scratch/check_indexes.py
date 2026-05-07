import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

# Add project root to path
sys.path.append(os.getcwd())

from app.config import settings

async def check_indexes():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    chunks = db.chunks
    
    print("--- Collection: chunks ---")
    async for index in chunks.list_indexes():
        print(index)
    
    # Check for search indexes (Atlas Search)
    # This requires a specific command or checking the Atlas UI
    # But we can try to see if $search fails in a dry run
    
    client.close()


if __name__ == "__main__":
    asyncio.run(check_indexes())
