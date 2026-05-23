import asyncio
from app.db.mongodb import MongoDB

async def check():
    await MongoDB.connect()
    chunks_col = MongoDB.get_collection("chunks")

    total = await chunks_col.count_documents({"contract_id": "airport_food_contract"})
    with_emb = await chunks_col.count_documents({"contract_id": "airport_food_contract", "embedding": {"$exists": True, "$type": "array", "$ne": []}})

    print(f"Total chunks: {total}")
    print(f"Chunks with embeddings: {with_emb}")

    if with_emb > 0:
        print("Testing vector index...")
        try:
            sample = await chunks_col.find_one({"embedding": {"$exists": True}})
            emb = sample["embedding"]
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "chunk_embedding_index",
                        "queryVector": emb,
                        "path": "embedding",
                        "numCandidates": 10,
                        "limit": 5,
                    }
                }
            ]
            res = await chunks_col.aggregate(pipeline).to_list(5)
            print(f"Vector search returned {len(res)} results.")
        except Exception as e:
            print(f"Vector search failed: {e}")

    await MongoDB.close()

if __name__ == "__main__":
    asyncio.run(check())
