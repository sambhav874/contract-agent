import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def create():
    # Read URI from environment or config
    uri = "mongodb+srv://sambhavjain874_db_user:DTulLZiBXqM9Pdsz@cluster0.xabdeis.mongodb.net/"
    client = AsyncIOMotorClient(uri)
    db = client.contract_agent

    print("Checking collection chunks indexes...")
    chunks = db.chunks

    vector_search_def = {
        "definition": {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 1024,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "contract_id"},
                {"type": "filter", "path": "chunk_level"},
                {"type": "filter", "path": "section_type_tags"},
            ]
        },
        "name": "chunk_embedding_index",
        "type": "vectorSearch"
    }

    print("Creating vectorSearch index 'chunk_embedding_index' on remote cluster...")
    try:
        res = await db.command({
            "createSearchIndexes": "chunks",
            "indexes": [vector_search_def]
        })
        print("Vector index response:", res)
    except Exception as e:
        print("Error creating vector index:", e)

    default_search_def = {
        "definition": {
            "mappings": {
                "dynamic": True
            }
        },
        "name": "default",
        "type": "search"
    }

    print("Creating search index 'default' on remote cluster...")
    try:
        res = await db.command({
            "createSearchIndexes": "chunks",
            "indexes": [default_search_def]
        })
        print("Search index response:", res)
    except Exception as e:
        print("Error creating search index:", e)

    client.close()

if __name__ == "__main__":
    asyncio.run(create())
