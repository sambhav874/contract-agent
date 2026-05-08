"""MongoDB hybrid search retriever with RRF, deduplication, structural boosting, and Voyage rerank-2.5."""

import asyncio
import os
import re
from typing import Any

import voyageai

from app.config import settings

from app.db.mongodb import MongoDB
from app.ingestion.embedder import embed_query


class Retriever:
    """
    MongoDB hybrid search retriever.

    Combines three search strategies via Reciprocal Rank Fusion (RRF):
    1. Semantic vector search (Voyage AI embeddings)
    2. Lexical full-text search (Atlas Search)
    3. Structural path matching (exact section lookups)

    Structural results are boosted because structural tags from the query plan
    are high-precision signals (e.g., "Section 4.08", "Article IV").
    """

    VECTOR_INDEX = "chunk_embedding_index"
    DEFAULT_CANDIDATE_POOL = 200
    RRF_K = 60
    DEFAULT_TOP_K = 15
    RERANK_MODEL = "rerank-2.5"
    RERANK_BATCH_SIZE = 20

    def __init__(self):
        self.vector_index = self.VECTOR_INDEX
        self._voyage_client: voyageai.Client | None = None

    @property
    def voyage_client(self) -> voyageai.Client:
        if self._voyage_client is None:
            api_key = os.getenv("VOYAGE_API_KEY", settings.voyage_api_key)
            self._voyage_client = voyageai.Client(
                api_key=api_key,
                base_url="https://ai.mongodb.com/v1",
            )
        return self._voyage_client

    # ------------------------------------------------------------------ #
    # Public interface                                                      #
    # ------------------------------------------------------------------ #

    async def fetch(
        self,
        contract_id: str,
        query: str,
        tags: list[str] | None = None,
        levels: list[str] | None = None,
        top_k: int = 15,
        enable_rerank: bool = True,
        enable_expansion: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant chunks using hybrid RRF search.

        Args:
            contract_id: Contract to search within.
            query: Natural language query for semantic + lexical search.
            tags: Section type tags OR structural paths to prioritise.
            levels: Chunk levels to include (macro/meso/micro). None = all.
            top_k: Maximum chunks to return.
            enable_rerank: Run Voyage rerank-2.5 on RRF results.
            enable_expansion: Use LLM query expansion before embedding.

        Returns:
            Ranked list of chunk dicts (embedding field excluded).
        """
        # ── Optional query expansion ──────────────────────────────────────
        effective_query = query
        semantic_keywords: list[str] = []
        if enable_expansion:
            from app.retrieval.query_expansion import expand_query
            expansion = await expand_query(query)
            effective_query = expansion.get("expanded_query", query)
            semantic_keywords = expansion.get("key_terms", [])

        # Separate semantic tags from structural path hints
        filter_tags: list[str] = []
        structural_hints: list[str] = []
        if tags:
            for t in tags:
                if self._is_structural_hint(t):
                    structural_hints.append(t)
                else:
                    filter_tags.append(t)

        pool = max(self.DEFAULT_CANDIDATE_POOL, top_k * 2)

        async def _empty_list():
            return []

        query_embedding = await embed_query(effective_query)

        # Run all three searches in parallel
        # Note: we ONLY filter by explicitly passed filter_tags, NOT semantic_keywords
        vector_task = self._vector_search(contract_id, query_embedding, filter_tags, levels, pool)
        keyword_task = self._keyword_search(contract_id, effective_query, filter_tags, levels, pool, keywords=semantic_keywords)
        struct_task = (
            self._structural_search(contract_id, structural_hints, levels, pool)
            if structural_hints else _empty_list()
        )

        vector_results, keyword_results, struct_results = await asyncio.gather(
            vector_task, keyword_task, struct_task
        )

        # Apply RRF with structural boost
        fused = self._apply_rrf(
            [
                (vector_results, 1.0),
                (keyword_results, 1.0),
                (struct_results, 2.5),   # structural matches are high-precision
            ],
            top_k=top_k,
        )

        if enable_rerank:
            fused = await self._rerank_voyage(query, fused, top_k=top_k)

        # Hard fallback: if nothing came back, return first N chunks
        if not fused:
            collection = MongoDB.get_collection("chunks")
            flt: dict[str, Any] = {"contract_id": contract_id}
            if levels:
                flt["chunk_level"] = {"$in": levels}
            fused = await collection.find(flt, {"embedding": 0}).limit(top_k).to_list(top_k)

        return fused

    async def fetch_by_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch specific chunks by their IDs."""
        collection = MongoDB.get_collection("chunks")
        return await collection.find(
            {"chunk_id": {"$in": chunk_ids}},
            {"embedding": 0},
        ).to_list(None)

    async def fetch_by_section(
        self,
        contract_id: str,
        section_tags: list[str],
        levels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch chunks by section type tags (used for targeted lookups)."""
        flt: dict[str, Any] = {
            "contract_id": contract_id,
            "section_type_tags": {"$in": section_tags},
        }
        if levels:
            flt["chunk_level"] = {"$in": levels}
        collection = MongoDB.get_collection("chunks")
        return await collection.find(flt, {"embedding": 0}).to_list(100)

    async def fetch_all_sections(self, contract_id: str) -> list[dict[str, Any]]:
        """Fetch all macro-level chunks for a map pass."""
        collection = MongoDB.get_collection("chunks")
        return await collection.find(
            {"contract_id": contract_id, "chunk_level": "macro"},
            {"embedding": 0},
        ).to_list(200)

    # ------------------------------------------------------------------ #
    # Search backends                                                       #
    # ------------------------------------------------------------------ #

    async def _vector_search(
        self,
        contract_id: str,
        embedding: list[float],
        tags: list[str] | None,
        levels: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Semantic vector search using Atlas $vectorSearch."""
        vector_filter: dict[str, Any] = {"contract_id": contract_id}
        if tags:
            vector_filter["section_type_tags"] = {"$in": tags}
        if levels:
            vector_filter["chunk_level"] = {"$in": levels}

        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.VECTOR_INDEX,
                    "queryVector": embedding,
                    "path": "embedding",
                    "filter": vector_filter,
                    "numCandidates": limit * 4,
                    "limit": limit,
                }
            },
            {"$addFields": {"vector_score": {"$meta": "vectorSearchScore"}}},
            {"$project": {"embedding": 0}},
        ]

        collection = MongoDB.get_collection("chunks")
        try:
            return await collection.aggregate(pipeline).to_list(limit)
        except Exception:
            return []

    async def _keyword_search(
        self,
        contract_id: str,
        query: str,
        tags: list[str] | None,
        levels: list[str] | None,
        limit: int,
        keywords: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Lexical search using Atlas full-text search, with robust regex fallback."""
        must_filters: list[dict[str, Any]] = [
            {"text": {"query": contract_id, "path": "contract_id"}}
        ]
        if tags:
            must_filters.append({"text": {"query": " ".join(tags), "path": "section_type_tags"}})

        pipeline: list[dict[str, Any]] = [
            {
                "$search": {
                    "index": "default",
                    "compound": {
                        "must": [{"text": {"query": query, "path": "text"}}],
                        "filter": must_filters,
                    },
                }
            },
            {"$addFields": {"keyword_score": {"$meta": "searchScore"}}},
            {"$project": {"embedding": 0}},
            {"$limit": limit},
        ]

        collection = MongoDB.get_collection("chunks")
        try:
            results = await collection.aggregate(pipeline).to_list(limit)
            if results:
                return results
        except Exception:
            pass

        # Fallback: more robust multi-keyword regex search
        search_keywords = keywords if keywords else [k for k in re.split(r"[\s,]+", query) if len(k) > 3]
        if not search_keywords:
            search_keywords = [query[:100]]

        # Use an $or search for keywords to increase recall in fallback
        # We search both in 'text' and 'structural_path'
        regex_clauses = []
        for kw in search_keywords[:8]:  # Increase to 8 keywords
            escaped = re.escape(kw)
            regex_clauses.append({"text": {"$regex": escaped, "$options": "i"}})
            regex_clauses.append({"structural_path": {"$regex": escaped, "$options": "i"}})

        regex_filter: dict[str, Any] = {
            "contract_id": contract_id,
            "$or": regex_clauses
        }
        if levels:
            regex_filter["chunk_level"] = {"$in": levels}
        
        return await collection.find(regex_filter, {"embedding": 0}).limit(limit).to_list(limit)

    async def _structural_search(
        self,
        contract_id: str,
        structural_hints: list[str],
        levels: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Exact structural path matching.

        Matches against `structural_path` field using case-insensitive regex.
        This catches section-level hints like "Article IV", "Section 4.08",
        "Exhibit B" that would be diluted by semantic search.
        """
        if not structural_hints:
            return []

        or_clauses: list[dict[str, Any]] = [
            {"structural_path": {"$regex": re.escape(hint), "$options": "i"}}
            for hint in structural_hints
        ]

        flt: dict[str, Any] = {"contract_id": contract_id, "$or": or_clauses}
        if levels:
            flt["chunk_level"] = {"$in": levels}

        collection = MongoDB.get_collection("chunks")
        return await collection.find(flt, {"embedding": 0}).limit(limit).to_list(limit)

    # ------------------------------------------------------------------ #
    # Reranking                                                             #
    # ------------------------------------------------------------------ #

    async def _rerank_voyage(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Second-pass reranking with Voyage rerank-2.5.

        Sends top-RMF candidates through Voyage's cross-encoder reranker
        and returns re-ordered results with ``relevance_score`` attached.
        """
        if not candidates:
            return []

        documents = [c.get("text", "") for c in candidates]
        rerank_k = min(self.RERANK_BATCH_SIZE * 2, len(documents))

        try:
            loop = asyncio.get_event_loop()
            reranking = await loop.run_in_executor(
                None,
                lambda: self.voyage_client.rerank(
                    query=query,
                    documents=documents,
                    model=self.RERANK_MODEL,
                    top_k=rerank_k,
                ),
            )
        except Exception:
            # Fail open — return original RRF ordering on any error
            return candidates

        # Map reranker output back to candidate docs
        idx_map = {r.index: r for r in reranking.results}
        reranked: list[dict[str, Any]] = []
        for i, doc in enumerate(candidates):
            if i in idx_map:
                doc = dict(doc)  # shallow copy
                doc["relevance_score"] = round(idx_map[i].relevance_score, 6)
                reranked.append(doc)

        # Slice after sorting by relevance_score descending
        return sorted(reranked, key=lambda d: d.get("relevance_score", 0.0), reverse=True)[:top_k]

    # ------------------------------------------------------------------ #
    # RRF fusion                                                            #
    # ------------------------------------------------------------------ #

    def _apply_rrf(
        self,
        result_lists: list[tuple[list[dict[str, Any]], float]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Reciprocal Rank Fusion.

        score(doc) = Σ weight_i / (RRF_K + rank_i)

        Higher RRF_K = more smoothing; lower = more weight to top results.
        """
        scores: dict[str, float] = {}
        chunk_map: dict[str, dict[str, Any]] = {}

        for result_list, weight in result_lists:
            for rank, chunk in enumerate(result_list):
                cid = chunk.get("chunk_id") or str(chunk.get("_id", ""))
                if not cid:
                    continue
                if cid not in chunk_map:
                    chunk_map[cid] = dict(chunk)  # shallow copy to avoid mutating originals
                scores[cid] = scores.get(cid, 0.0) + weight / (self.RRF_K + rank + 1)

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        final: list[dict[str, Any]] = []
        for cid in sorted_ids[:top_k]:
            doc = dict(chunk_map[cid])  # fresh copy per reuse
            doc["rrf_score"] = round(scores[cid], 6)
            final.append(doc)

        return final

    # ------------------------------------------------------------------ #
    # Helpers                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_structural_hint(tag: str) -> bool:
        """
        Returns True if a tag looks like a structural path (Article, Section, Exhibit…)
        rather than a semantic section type tag.
        """
        structural_keywords = (
            "article", "section", "exhibit", "schedule", "appendix",
            "annex", "clause", "part ", "§",
        )
        tl = tag.lower()
        return any(tl.startswith(kw) for kw in structural_keywords) or bool(
            re.match(r"^\d+\.\d+", tag)
        )


# ------------------------------------------------------------------ #
# Singleton                                                             #
# ------------------------------------------------------------------ #

_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    """Get or create the global retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def format_chunks_for_context(chunks: list[dict[str, Any]]) -> str:
    """
    Format retrieved chunks into a structured context string for the LLM.

    Each chunk is formatted with its metadata header followed by the text.
    Chunks are separated by a visual divider for easy parsing.
    """
    if not chunks:
        return "[No chunks retrieved]"

    parts: list[str] = []
    for chunk in chunks:
        cid = chunk.get("chunk_id", "unknown")
        path = chunk.get("structural_path", "unknown")
        level = chunk.get("chunk_level", "unknown")
        tags = ", ".join(chunk.get("section_type_tags", [])) or "none"
        rrf = chunk.get("rrf_score", "")
        rrf_str = f" | RRF:{rrf:.4f}" if rrf else ""
        char_range = f"{chunk.get('char_start', 0)}-{chunk.get('char_end', 0)}"
        text = chunk.get("text", "")

        parts.append(
            f"[CHUNK: {cid}]\n"
            f"[PATH: {path}]\n"
            f"[RANGE: {char_range} | LEVEL: {level} | TAGS: {tags}{rrf_str}]\n"
            f"{text}\n"
            f"{'─' * 60}"
        )

    return "\n".join(parts)