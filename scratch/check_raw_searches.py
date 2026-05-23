import asyncio
from app.db.mongodb import MongoDB
from app.retrieval.retriever import get_retriever

async def check():
    await MongoDB.connect()
    retriever = get_retriever()

    query = "Under what conditions can the Client terminate the agreement for cause?"
    print(f"QUERY: {query}\n")

    # 1. Expand query
    from app.retrieval.query_expansion import expand_query
    expansion = await expand_query(query)
    effective_query = expansion.get("expanded_query", query)
    semantic_keywords = expansion.get("key_terms", [])
    print(f"Effective Query: {effective_query}")
    print(f"Keywords: {semantic_keywords}\n")

    # 2. Vector search
    from app.ingestion.embedder import embed_query
    query_embedding = await embed_query(effective_query)

    vector_results = await retriever._vector_search("prod-logistics-v3", query_embedding, [], None, 10)
    print(f"Vector search results: {len(vector_results)}")
    for r in vector_results:
        print(f"  - {r.get('structural_path')} (vector score: {r.get('vector_score')})")

    # 3. Keyword search
    keyword_results = await retriever._keyword_search("prod-logistics-v3", effective_query, [], None, 10, keywords=semantic_keywords)
    print(f"\nKeyword search results: {len(keyword_results)}")
    for r in keyword_results:
        print(f"  - {r.get('structural_path')} (keyword score: {r.get('keyword_score')})")

    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
