"""
MongoDB hybrid search retriever with RRF, deduplication,
structural boosting, and Voyage rerank-2.5.

Fixes applied vs. original:
  1. Hard fallback no longer returns arbitrary first-N chunks.
     It now returns macro-level chunks sorted by char_start (document
     order) and emits a retrieval_degraded signal in the returned docs
     so the agent can caveat its answer.
  2. Query expansion key_terms are now wired into the PRIMARY Atlas
     $search pipeline via a compound.should clause, not just the regex
     fallback. Expansion is no longer wasted on the primary path.
  3. Added per-call latency and result-count logging so cost/quality
     regressions are visible in production.
  4. _keyword_search fallback uses $or across both text and structural_path
     (was already correct) but now also respects the levels filter that
     was previously dropped in the regex path.
  5. _rerank_voyage now logs when it falls back to RRF order so silent
     Voyage errors don't hide quality degradation.
  6. fetch() docstring updated to reflect the degradation signal.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any

import voyageai

from app.config import settings
from app.db.mongodb import MongoDB
from app.ingestion.embedder import embed_query
from app.observability.logger import get_logger

logger = get_logger(__name__)

# Sentinel tag added to chunks when retrieval fell back to document-order
# scanning. The agent layer checks for this and caveats its answer.
DEGRADED_RETRIEVAL_TAG = "__retrieval_degraded__"


class Retriever:
    """
    MongoDB hybrid search retriever.

    Combines three search strategies via Reciprocal Rank Fusion (RRF):
      1. Semantic vector search  (Voyage AI embeddings)
      2. Lexical full-text search (Atlas Search, with expanded terms)
      3. Structural path matching (exact section lookups)

    Structural results are boosted (weight 2.5) because structural tags from
    the query plan are high-precision signals (e.g. "Section 4.08").

    When all three strategies return empty, the fallback returns macro-level
    chunks in document order (sorted by char_start) tagged with
    DEGRADED_RETRIEVAL_TAG so callers can detect the degradation.
    """

    VECTOR_INDEX = "chunk_embedding_index"
    DEFAULT_CANDIDATE_POOL = 200
    RRF_K = 60
    DEFAULT_TOP_K = 15
    RERANK_MODEL = "rerank-2.5"
    RERANK_BATCH_SIZE = 20

    def __init__(self) -> None:
        self.vector_index = self.VECTOR_INDEX
        self._voyage_client: voyageai.Client | None = None

    # ── Voyage client (lazy, singleton) ──────────────────────────────────────

    @property
    def voyage_client(self) -> voyageai.Client:
        if self._voyage_client is None:
            api_key = os.getenv("VOYAGE_API_KEY", settings.voyage_api_key)
            self._voyage_client = voyageai.Client(
                api_key=api_key,
                base_url="https://ai.mongodb.com/v1",
            )
        return self._voyage_client

    # ── Public interface ──────────────────────────────────────────────────────

    async def fetch(
        self,
        contract_id: str,
        query: str,
        tags: list[str] | None = None,
        levels: list[str] | None = None,
        top_k: int = DEFAULT_TOP_K,
        enable_rerank: bool = True,
        enable_expansion: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant chunks using hybrid RRF search.

        Args:
            contract_id:      Contract to search within.
            query:            Natural language query.
            tags:             Section type tags OR structural paths to prioritise.
            levels:           Chunk levels to include (macro/meso/micro). None = all.
            top_k:            Maximum chunks to return.
            enable_rerank:    Run Voyage rerank-2.5 on RRF results.
            enable_expansion: Use LLM query expansion before embedding.

        Returns:
            Ranked list of chunk dicts (embedding field excluded).
            If retrieval degraded (all strategies empty), chunks are tagged
            with section_type_tags containing DEGRADED_RETRIEVAL_TAG.
        """
        t0 = time.monotonic()

        # ── Optional query expansion ──────────────────────────────────────
        effective_query = query
        semantic_keywords: list[str] = []
        if enable_expansion:
            try:
                from app.retrieval.query_expansion import expand_query
                expansion = await expand_query(query)
                effective_query = expansion.get("expanded_query", query)
                semantic_keywords = expansion.get("key_terms", [])
            except Exception as exc:
                logger.warning("query_expansion_failed", error=str(exc))

        # ── Separate semantic tags from structural path hints ─────────────
        filter_tags: list[str] = []
        structural_hints: list[str] = []
        if tags:
            for t in tags:
                (structural_hints if self._is_structural_hint(t) else filter_tags).append(t)

        pool = max(self.DEFAULT_CANDIDATE_POOL, top_k * 2)

        async def _empty() -> list:
            return []

        query_embedding = await embed_query(effective_query)

        # ── Run all three searches in parallel ────────────────────────────
        vector_task   = self._vector_search(contract_id, query_embedding, filter_tags, levels, pool)
        keyword_task  = self._keyword_search(
            contract_id, effective_query, filter_tags, levels, pool,
            keywords=semantic_keywords,           # now used in primary path too
        )
        struct_task   = (
            self._structural_search(contract_id, structural_hints, levels, pool)
            if structural_hints else _empty()
        )

        vector_results, keyword_results, struct_results = await asyncio.gather(
            vector_task, keyword_task, struct_task
        )

        logger.debug(
            "retrieval_raw_counts",
            contract_id=contract_id,
            vector=len(vector_results),
            keyword=len(keyword_results),
            structural=len(struct_results),
        )

        # ── RRF fusion ────────────────────────────────────────────────────
        fused = self._apply_rrf(
            [
                (vector_results,  1.0),
                (keyword_results, 1.5),
                (struct_results,  3.0),   # structural matches are high-precision
            ],
            top_k=top_k,
        )

        if enable_rerank and fused:
            fused = await self._rerank_voyage(query, fused, top_k=top_k)

        # ── Graceful degradation fallback ─────────────────────────────────
        if not fused:
            fused = await self._degraded_fallback(contract_id, levels, top_k)

        elapsed = time.monotonic() - t0
        logger.info(
            "retrieval_complete",
            contract_id=contract_id,
            query_preview=query[:80],
            chunks_returned=len(fused),
            degraded=any(DEGRADED_RETRIEVAL_TAG in c.get("section_type_tags", []) for c in fused),
            elapsed_ms=round(elapsed * 1000),
        )

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
        """Fetch chunks by section type tags."""
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

    # ── Search backends ───────────────────────────────────────────────────────

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
        # We intentionally do NOT filter by tags here. Vector search is a semantic safety net.
        # Hard-filtering by tags causes vector=0 if the LLM guesses the wrong section tag.
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
        except Exception as exc:
            logger.warning("vector_search_failed", error=str(exc))
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
        """
        Lexical search using Atlas full-text search.

        FIX: expanded key_terms are now included in the primary Atlas pipeline
        via a compound.should clause so expansion actually improves primary
        recall, not just the regex fallback.
        """
        must_filters: list[dict[str, Any]] = [
            {"text": {"query": contract_id, "path": "contract_id"}}
        ]
        # We intentionally do NOT filter by tags here for max recall.
        if levels:
            must_filters.append(
                {"text": {"query": " ".join(levels), "path": "chunk_level"}}
            )

        # Build should clauses to boost expanded key terms
        should_clauses: list[dict[str, Any]] = []
        if keywords:
            for kw in keywords[:10]:
                should_clauses.append({"text": {"query": kw, "path": "text", "score": {"boost": {"value": 1.5}}}})

        compound_query: dict[str, Any] = {
            "must": [{"text": {"query": query, "path": "text"}}],
            "filter": must_filters,
        }
        if should_clauses:
            compound_query["should"] = should_clauses

        pipeline: list[dict[str, Any]] = [
            {
                "$search": {
                    "index": "default",
                    "compound": compound_query,
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
        except Exception as exc:
            logger.warning("atlas_keyword_search_failed", error=str(exc))

        # ── Regex fallback ────────────────────────────────────────────────
        # Use all available keywords (expanded + split from query) for maximum
        # recall. Levels filter is respected here (was missing in original).
        search_keywords = keywords if keywords else [
            k for k in re.split(r"[\s,]+", query) if len(k) > 3
        ]
        if not search_keywords:
            search_keywords = [query[:100]]

        regex_clauses: list[dict[str, Any]] = []
        for kw in search_keywords[:8]:
            escaped = re.escape(kw)
            regex_clauses.append({"text":            {"$regex": escaped, "$options": "i"}})
            regex_clauses.append({"structural_path": {"$regex": escaped, "$options": "i"}})

        regex_filter: dict[str, Any] = {
            "contract_id": contract_id,
            "$or": regex_clauses,
        }
        if levels:
            regex_filter["chunk_level"] = {"$in": levels}

        try:
            return await collection.find(
                regex_filter, {"embedding": 0}
            ).limit(limit).to_list(limit)
        except Exception as exc:
            logger.warning("regex_keyword_fallback_failed", error=str(exc))
            return []

    async def _structural_search(
        self,
        contract_id: str,
        structural_hints: list[str],
        levels: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Exact structural path matching.

        Matches against `structural_path` using case-insensitive regex.
        High precision for section-level hints like "Article IV", "Section 4.08".
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
        try:
            return await collection.find(flt, {"embedding": 0}).limit(limit).to_list(limit)
        except Exception as exc:
            logger.warning("structural_search_failed", error=str(exc))
            return []

    # ── Graceful degradation fallback ─────────────────────────────────────────

    async def _degraded_fallback(
        self,
        contract_id: str,
        levels: list[str] | None,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Called only when ALL three search strategies return empty.

        Returns macro-level chunks in document order (sorted by char_start)
        so the model at least sees the beginning of the contract rather than
        arbitrary rows.  Every returned chunk is tagged with
        DEGRADED_RETRIEVAL_TAG so the agent can detect and caveat the result.

        FIX (vs. original): original did collection.find({}) with no sort —
        completely random ordering, high hallucination risk.
        """
        logger.warning(
            "retrieval_degraded_fallback_triggered",
            contract_id=contract_id,
            levels=levels,
        )

        fallback_levels = levels or ["macro"]
        collection = MongoDB.get_collection("chunks")
        try:
            chunks = await collection.find(
                {"contract_id": contract_id, "chunk_level": {"$in": fallback_levels}},
                {"embedding": 0},
            ).sort("char_start", 1).limit(top_k).to_list(top_k)
        except Exception as exc:
            logger.error("degraded_fallback_failed", error=str(exc))
            return []

        # Tag each chunk so the agent knows retrieval degraded
        for chunk in chunks:
            tags = list(chunk.get("section_type_tags") or [])
            if DEGRADED_RETRIEVAL_TAG not in tags:
                tags.append(DEGRADED_RETRIEVAL_TAG)
            chunk["section_type_tags"] = tags

        return chunks

    # ── Reranking ─────────────────────────────────────────────────────────────

    async def _rerank_voyage(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Second-pass reranking with Voyage rerank-2.5.

        FIX: logs explicitly when falling back to RRF order so silent Voyage
        errors don't hide quality degradation in production.
        """
        if not candidates:
            return []

        documents = [c.get("text", "") for c in candidates]
        rerank_k = min(top_k, len(documents))

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
        except Exception as exc:
            logger.warning(
                "voyage_rerank_failed_falling_back_to_rrf",
                error=str(exc),
                candidate_count=len(candidates),
            )
            return candidates  # fail open — return original RRF ordering

        idx_map = {r.index: r for r in reranking.results}
        reranked: list[dict[str, Any]] = []
        for i, doc in enumerate(candidates):
            if i in idx_map:
                doc = dict(doc)
                doc["relevance_score"] = round(idx_map[i].relevance_score, 6)
                reranked.append(doc)

        return sorted(reranked, key=lambda d: d.get("relevance_score", 0.0), reverse=True)[:top_k]

    # ── RRF fusion ────────────────────────────────────────────────────────────

    def _apply_rrf(
        self,
        result_lists: list[tuple[list[dict[str, Any]], float]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Reciprocal Rank Fusion.

        score(doc) = Σ weight_i / (RRF_K + rank_i)
        """
        scores: dict[str, float] = {}
        chunk_map: dict[str, dict[str, Any]] = {}

        for result_list, weight in result_lists:
            for rank, chunk in enumerate(result_list):
                cid = chunk.get("chunk_id") or str(chunk.get("_id", ""))
                if not cid:
                    continue
                if cid not in chunk_map:
                    chunk_map[cid] = dict(chunk)
                scores[cid] = scores.get(cid, 0.0) + weight / (self.RRF_K + rank + 1)

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        final: list[dict[str, Any]] = []
        for cid in sorted_ids[:top_k]:
            doc = dict(chunk_map[cid])
            doc["rrf_score"] = round(scores[cid], 6)
            final.append(doc)

        return final

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_structural_hint(tag: str) -> bool:
        """
        Returns True if a tag looks like a structural path rather than a
        semantic section type tag.
        """
        structural_keywords = (
            "article", "section", "exhibit", "schedule", "appendix",
            "annex", "clause", "part ", "§",
        )
        tl = tag.lower()
        return any(tl.startswith(kw) for kw in structural_keywords) or bool(
            re.match(r"^\d+\.\d+", tag)
        )


# ── Singleton ─────────────────────────────────────────────────────────────────

_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    """Get or create the global retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


# ── Context formatter ─────────────────────────────────────────────────────────

def format_chunks_for_context(chunks: list[dict[str, Any]]) -> str:
    """
    Format retrieved chunks into a structured context string for the LLM.

    Prepends a degradation warning when retrieval fell back to document-order
    scanning so the model knows to caveat its answer.
    """
    if not chunks:
        return "[No chunks retrieved]"

    degraded = any(DEGRADED_RETRIEVAL_TAG in c.get("section_type_tags", []) for c in chunks)
    header = (
        "⚠️  RETRIEVAL DEGRADED: semantic and keyword search returned no results. "
        "The following chunks are from document-order fallback and may not be "
        "directly relevant. Caveat your answer accordingly.\n\n"
        if degraded else ""
    )

    parts: list[str] = []
    for chunk in chunks:
        cid   = chunk.get("chunk_id", "unknown")
        path  = chunk.get("structural_path", "unknown")
        level = chunk.get("chunk_level", "unknown")
        tags  = ", ".join(
            t for t in chunk.get("section_type_tags", [])
            if t != DEGRADED_RETRIEVAL_TAG
        ) or "none"
        rrf   = chunk.get("rrf_score", "")
        rrf_str = f" | RRF:{rrf:.4f}" if rrf else ""
        char_range = f"{chunk.get('char_start', 0)}-{chunk.get('char_end', 0)}"
        text  = chunk.get("text", "")

        parts.append(
            f"[CHUNK: {cid}]\n"
            f"[PATH: {path}]\n"
            f"[RANGE: {char_range} | LEVEL: {level} | TAGS: {tags}{rrf_str}]\n"
            f"{text}\n"
            f"{'─' * 60}"
        )

    return header + "\n".join(parts)