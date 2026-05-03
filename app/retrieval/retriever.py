"""MongoDB hybrid search retriever with fallback mechanisms."""

import asyncio
from typing import Any

from app.config import settings
from app.db.mongodb import MongoDB
from app.ingestion.embedder import embed_query


class Retriever:
    """MongoDB hybrid search retriever using vector + keyword search."""

    def __init__(self):
        self.vector_index = "chunk_embedding_index"

    async def fetch(
        self,
        contract_id: str,
        query: str,
        tags: list[str] | None = None,
        levels: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant chunks using hybrid search with Rank Fusion.
        Combines results from Vector Search, Keyword Search, and Structural Match.
        """
        # 1. Prepare search inputs
        query_embedding = await embed_query(query)
        
        semantic_tags = []
        structural_tags = []
        if tags:
            for t in tags:
                if any(x in t.upper() for x in ["ARTICLE", "SECTION", "EXHIBIT", "SCHEDULE", "APPENDIX"]):
                    structural_tags.append(t)
                else:
                    semantic_tags.append(t)

        # 2. Execute parallel searches
        # We fetch more candidates than top_k for better fusion quality
        candidate_pool = 50 
        
        vector_task = self._vector_search(contract_id, query_embedding, semantic_tags, limit=candidate_pool)
        keyword_task = self._keyword_search(contract_id, query, semantic_tags, limit=candidate_pool)
        
        # Structural search is high-precision, we fetch it too
        struct_results = []
        if structural_tags:
            struct_results = await self._structural_search(contract_id, structural_tags, limit=candidate_pool)

        vector_results, keyword_results = await asyncio.gather(vector_task, keyword_task)

        # 3. Apply Reciprocal Rank Fusion (RRF)
        # Weights can be tuned. Default is equal weighting (1.0).
        results = self._apply_rrf(
            search_results_lists=[
                (vector_results, 1.0),
                (keyword_results, 1.0),
                (struct_results, 2.0), # Boost structural matches
            ],
            top_k=top_k
        )

        # 4. Final Fallback
        if not results:
            collection = MongoDB.get_collection("chunks")
            results = await collection.find(
                {"contract_id": contract_id},
                {"embedding": 0},
            ).limit(top_k).to_list(top_k)

        return results

    async def _vector_search(
        self, 
        contract_id: str, 
        embedding: list[float], 
        tags: list[str] | None, 
        limit: int
    ) -> list[dict[str, Any]]:
        """Perform semantic vector search."""
        vector_filter: dict[str, Any] = {"contract_id": contract_id}
        if tags:
            vector_filter["section_type_tags"] = {"$in": tags}

        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.vector_index,
                    "queryVector": embedding,
                    "path": "embedding",
                    "filter": vector_filter,
                    "numCandidates": limit * 3,
                    "limit": limit,
                }
            },
            {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
            {"$project": {"embedding": 0}},
        ]
        
        collection = MongoDB.get_collection("chunks")
        return await collection.aggregate(pipeline).to_list(limit)

    async def _keyword_search(
        self,
        contract_id: str,
        query: str,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lexical search using Atlas full-text search."""
        filter_dict: dict[str, Any] = {"contract_id": contract_id}
        if tags:
            filter_dict["section_type_tags"] = {"$in": tags}

        pipeline = [
            {
                "$search": {
                    "index": "default",
                    "text": {
                        "query": query,
                        "path": "text",
                    },
                    "filter": filter_dict,
                }
            },
            {"$addFields": {"score": {"$meta": "searchScore"}}},
            {"$project": {"embedding": 0}},
            {"$limit": limit},
        ]

        collection = MongoDB.get_collection("chunks")
        try:
            return await collection.aggregate(pipeline).to_list(limit)
        except Exception:
            # Fallback to simple regex if Atlas search fails
            return await collection.find(
                {"contract_id": contract_id, "text": {"$regex": query, "$options": "i"}},
                {"embedding": 0}
            ).limit(limit).to_list(limit)

    async def _structural_search(
        self,
        contract_id: str,
        structural_tags: list[str],
        limit: int = 50
    ) -> list[dict[str, Any]]:
        """Direct match on structural paths (Article, Section, etc)."""
        collection = MongoDB.get_collection("chunks")
        or_filters = [{"structural_path": {"$regex": st, "$options": "i"}} for st in structural_tags]
        return await collection.find(
            {"contract_id": contract_id, "$or": or_filters},
            {"embedding": 0}
        ).limit(limit).to_list(limit)

    def _apply_rrf(
        self,
        search_results_lists: list[tuple[list[dict[str, Any]], float]],
        top_k: int,
        k: int = 60
    ) -> list[dict[str, Any]]:
        """
        Apply Reciprocal Rank Fusion to multiple result lists.
        Score = sum(weight / (k + rank))
        """
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, dict[str, Any]] = {}

        for results, weight in search_results_lists:
            for rank, chunk in enumerate(results):
                chunk_id = chunk.get("chunk_id") or str(chunk.get("_id"))
                if not chunk_id:
                    continue
                
                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = chunk
                
                # RRF Formula
                score = weight / (k + rank + 1)
                rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + score

        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        final_results = []
        for cid in sorted_ids[:top_k]:
            chunk = chunk_map[cid]
            chunk["rrf_score"] = rrf_scores[cid]
            final_results.append(chunk)
            
        return final_results

    async def fetch_by_ids(
        self,
        chunk_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch chunks by their IDs."""
        collection = MongoDB.get_collection("chunks")
        results = await collection.find(
            {"chunk_id": {"$in": chunk_ids}},
            {"embedding": 0},
        ).to_list(None)
        return results

    async def fetch_by_section(
        self,
        contract_id: str,
        section_tags: list[str],
        levels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch chunks by section type tags."""
        filter_dict: dict[str, Any] = {
            "contract_id": contract_id,
            "section_type_tags": {"$in": section_tags},
        }

        if levels:
            filter_dict["chunk_level"] = {"$in": levels}

        collection = MongoDB.get_collection("chunks")
        results = await collection.find(
            filter_dict,
            {"embedding": 0},
        ).to_list(50)  # Get more for section-based fetch

        return results

    async def fetch_all_sections(self, contract_id: str) -> list[dict[str, Any]]:
        """Fetch all chunks for a contract (for debugging/broad retrieval)."""
        collection = MongoDB.get_collection("chunks")
        results = await collection.find(
            {"contract_id": contract_id},
            {"embedding": 0},
        ).to_list(200)
        return results


# Global retriever instance
_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    """Get or create the retriever."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def format_chunks_for_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks for LLM context."""
    formatted = []

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", "unknown")
        path = chunk.get("structural_path", "unknown")
        char_start = chunk.get("char_start", 0)
        char_end = chunk.get("char_end", 0)
        level = chunk.get("chunk_level", "unknown")
        tags = ", ".join(chunk.get("section_type_tags", [])) or "none"
        text = chunk.get("text", "")

        formatted.append(f"""[CHUNK_ID: {chunk_id}]
[PATH: {path}]
[CHAR_RANGE: {char_start}-{char_end}]
[LEVEL: {level}]
[TAGS: {tags}]
{text}
---
""")

    return "\n".join(formatted)
