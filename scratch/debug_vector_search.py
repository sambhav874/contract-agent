import asyncio
from app.db.mongodb import MongoDB
from app.retrieval.retriever import get_retriever
from app.ingestion.embedder import embed_query

async def check():
    await MongoDB.connect()
    retriever = get_retriever()
    query_embedding = await embed_query("test query")

    vector_filter = {"contract_id": "prod-logistics-v3"}
    pipeline = [
        {
            "$vectorSearch": {
                "index": retriever.VECTOR_INDEX,
                "queryVector": query_embedding,
                "path": "embedding",
                "filter": vector_filter,
                "numCandidates": 40,
                "limit": 10,
            }
        },
        {"$addFields": {"vector_score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"embedding": 0}},
    ]

    collection = MongoDB.get_collection("chunks")
    try:
        results = await collection.aggregate(pipeline).to_list(10)
        print("Success, results count:", len(results))
    except Exception as e:
        print("EXCEPTION in vector search:")
        import traceback
        traceback.print_exc()

    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
