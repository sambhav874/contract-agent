"""MongoDB hybrid search retriever with fallback mechanisms."""

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
        Retrieve relevant chunks using hybrid search with fallback.

        Args:
            contract_id: Contract to search within
            query: User query or search term
            tags: Optional section type tags to filter on
            levels: Optional chunk levels to filter on
            top_k: Number of results to return

        Returns:
            List of retrieved chunks with scores
        """
        # Embed the query
        query_embedding = await embed_query(query)

        # Separate semantic tags from structural paths
        semantic_tags = []
        structural_tags = []
        if tags:
            for t in tags:
                if any(x in t.upper() for x in ["ARTICLE", "SECTION", "EXHIBIT", "SCHEDULE", "APPENDIX"]):
                    structural_tags.append(t)
                else:
                    semantic_tags.append(t)

        # Vector search only supports simple filters
        vector_filter: dict[str, Any] = {"contract_id": contract_id}
        if semantic_tags:
            vector_filter["section_type_tags"] = {"$in": semantic_tags}

        # 1. Vector search
        vector_filter: dict[str, Any] = {"contract_id": contract_id}
        if semantic_tags:
            vector_filter["section_type_tags"] = {"$in": semantic_tags}

        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.vector_index,
                    "queryVector": query_embedding,
                    "path": "embedding",
                    "filter": vector_filter,
                    "numCandidates": 150,
                    "limit": top_k,
                }
            },
            {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
            {"$project": {"embedding": 0}},
        ]
        
        collection = MongoDB.get_collection("chunks")
        results = await collection.aggregate(pipeline).to_list(top_k)

        # 2. Structural fetch (Direct match)
        if structural_tags:
            or_filters = [{"structural_path": {"$regex": st, "$options": "i"}} for st in structural_tags]
            struct_results = await collection.find(
                {"contract_id": contract_id, "$or": or_filters},
                {"embedding": 0}
            ).limit(top_k).to_list(top_k)
            
            # Combine and deduplicate
            existing_ids = {r.get("chunk_id") for r in results}
            for sr in struct_results:
                if sr.get("chunk_id") not in existing_ids:
                    results.append(sr)
                    existing_ids.add(sr.get("chunk_id"))

        # 3. FALLBACKS ... (rest of the logic)

        # FALLBACK 1: If vector search returns < 5 results, try keyword search
        if len(results) < 5:
            keyword_results = await self._keyword_search(
                contract_id=contract_id,
                query=query,
                tags=tags,
                top_k=top_k - len(results),
            )
            results.extend(keyword_results)

        # FALLBACK 2: If still < 5 results, fetch by section tags
        if len(results) < 5 and tags:
            section_results = await self.fetch_by_section(
                contract_id=contract_id,
                section_tags=tags,
                levels=levels,
            )
            # Add only if not already in results
            existing_ids = {r.get("chunk_id") for r in results}
            for sr in section_results:
                if sr.get("chunk_id") not in existing_ids:
                    results.append(sr)
                    existing_ids.add(sr.get("chunk_id"))

        # FALLBACK 3: If still no results, return all chunks for contract
        if len(results) == 0:
            all_chunks = await collection.find(
                {"contract_id": contract_id},
                {"embedding": 0},
            ).to_list(top_k)
            results = all_chunks

        return results

    async def _keyword_search(
        self,
        contract_id: str,
        query: str,
        tags: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Fallback keyword search using Atlas full-text search."""
        filter_dict: dict[str, Any] = {"contract_id": contract_id}

        if tags:
            filter_dict["section_type_tags"] = {"$in": tags}

        # Try full-text search first
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
            {"$sort": {"score": -1}},
            {"$project": {"embedding": 0}},
            {"$limit": top_k},
        ]

        collection = MongoDB.get_collection("chunks")
        try:
            results = await collection.aggregate(pipeline).to_list(top_k)
            return results
        except Exception:
            # Fallback to exact text match if full-text search not configured
            # Use regex for partial matching
            query_lower = query.lower()
            keywords = query_lower.split()[:5]  # First 5 words

            match_pipeline = []
            for kw in keywords:
                match_pipeline.append({
                    "$match": {
                        "contract_id": contract_id,
                        "text": {"$regex": kw, "$options": "i"}
                    }
                })

            if match_pipeline:
                # Combine with $or
                or_pipeline = [{
                    "$match": {
                        "contract_id": contract_id,
                        "$or": [{"text": {"$regex": kw, "$options": "i"}} for kw in keywords]
                    }
                }, {"$limit": top_k}]

                try:
                    results = await collection.aggregate(or_pipeline).to_list(top_k)
                    return results
                except Exception:
                    pass

            # Last resort: return first N chunks
            return await collection.find(
                {"contract_id": contract_id},
                {"embedding": 0},
            ).limit(top_k).to_list(top_k)

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
