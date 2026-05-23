import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def create():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.contract_agent
    chunks = db.chunks

    print("Creating vectorSearch index 'chunk_embedding_index'...")
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

    try:
        res = await db.command({
            "createSearchIndexes": "chunks",
            "indexes": [vector_search_def]
        })
        print("Vector index response:", res)
    except Exception as e:
        print("Error creating vector index:", e)

    print("\nCreating full-text search index 'default'...")
    default_search_def = {
        "definition": {
            "mappings": {
                "dynamic": True
            }
        },
        "name": "default",
        "type": "search"
    }

    try:
        res = await db.command({
            "createSearchIndexes": "chunks",
            "indexes": [default_search_def]
        })
        print("Full-text search index response:", res)
    except Exception as e:
        print("Error creating full-text search index:", e)

    client.close()

if __name__ == "__main__":
    asyncio.run(create())
