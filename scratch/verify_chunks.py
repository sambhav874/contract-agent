import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.db.mongodb import MongoDB

async def verify():
    await MongoDB.connect()
    chunks_col = MongoDB.get_collection("chunks")
    count = await chunks_col.count_documents({"contract_id": "airport_agreement_2025"})
    print(f"Total Chunks: {count}")
    
    if count > 0:
        chunk = await chunks_col.find_one({"contract_id": "airport_agreement_2025"})
        print(f"Sample Chunk ID: {chunk.get('chunk_id')}")
        print(f"Sample Chunk Text: {chunk.get('text')[:100]}...")
        print(f"Sample Chunk Level: {chunk.get('chunk_level')}")
    
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(verify())
