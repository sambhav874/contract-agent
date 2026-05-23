"""
LangChain-compatible wrapper around the contract-agent hybrid retriever.

Why this exists
---------------
Our native Retriever (retriever.py) is production-optimised with RRF, structural
boosting and async motor queries.  LangChain's evaluation chains (and RAGAS) expect
a ``BaseRetriever`` interface.  This module provides:

1. ``VoyageAILangChainEmbeddings`` – a thin LangChain ``Embeddings`` adapter that
   delegates to our existing EmbeddingService so we never touch OpenAI.

2. ``ContractHybridRetriever`` – a ``BaseRetriever`` subclass that calls our native
   ``Retriever.fetch()`` and converts the results into LangChain ``Document`` objects.

3. ``get_langchain_retriever(contract_id, ...)`` – factory used by the evaluation
   module and any LangChain chain that needs contract-scoped retrieval.
"""

from __future__ import annotations

import asyncio
from typing import Any, List

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.ingestion.embedder import get_embedding_service
from app.retrieval.retriever import get_retriever


# ── LangChain Embeddings adapter ─────────────────────────────────────────────

class VoyageAILangChainEmbeddings(Embeddings):
    """
    Thin adapter that wraps our VoyageAI ``EmbeddingService`` as a LangChain
    ``Embeddings`` object.

    This avoids pulling in ``langchain-voyageai`` or ``openai`` as dependencies
    while keeping full compatibility with LangChain chains and evaluators.

    Sync methods call the VoyageAI SDK directly (blocking HTTP) so they are
    safe to call both inside and outside an asyncio event loop.
    """

    def _sync_embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        """Direct synchronous call to VoyageAI — no event loop required."""
        import voyageai
        from app.config import settings
        client = voyageai.Client(
            api_key=settings.voyage_api_key,
            base_url="https://ai.mongodb.com/v1",
        )
        return client.embed(texts, model=settings.voyage_model, input_type=input_type).embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents (sync — safe inside or outside event loops)."""
        return self._sync_embed(texts, "document")

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query (sync — safe inside or outside event loops)."""
        return self._sync_embed([text], "query")[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Async embed documents."""
        service = get_embedding_service()
        return await service.embed_documents(texts, input_type="document")

    async def aembed_query(self, text: str) -> list[float]:
        """Async embed a single query."""
        service = get_embedding_service()
        return await service.embed_query(text)


# ── LangChain BaseRetriever adapter ──────────────────────────────────────────

class ContractHybridRetriever(BaseRetriever):
    """
    LangChain ``BaseRetriever`` backed by our hybrid RRF search.

    Fields are Pydantic v1/v2-compatible (langchain-core uses Pydantic internally).
    The ``contract_id`` field scopes every retrieval call to a single contract.

    Metadata from each chunk (structural_path, chunk_level, tags, rrf_score) is
    preserved in ``Document.metadata`` so evaluation metrics can inspect provenance.
    """

    contract_id: str
    tags: list[str] | None = None
    levels: list[str] | None = None
    top_k: int = 15

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(self, query: str, **kwargs: Any) -> List[Document]:
        """Sync retrieval (runs the async method in an event loop)."""
        return asyncio.get_event_loop().run_until_complete(
            self._aget_relevant_documents(query, **kwargs)
        )

    async def _aget_relevant_documents(
        self, query: str, **kwargs: Any
    ) -> List[Document]:
        """Async retrieval – calls our native hybrid RRF retriever."""
        retriever = get_retriever()
        chunks = await retriever.fetch(
            contract_id=self.contract_id,
            query=query,
            tags=self.tags,
            levels=self.levels,
            top_k=self.top_k,
        )
        return [_chunk_to_document(chunk) for chunk in chunks]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _chunk_to_document(chunk: dict[str, Any]) -> Document:
    """Convert a raw chunk dict into a LangChain ``Document``."""
    text = chunk.get("text", "")
    metadata = {
        "chunk_id": chunk.get("chunk_id", ""),
        "contract_id": chunk.get("contract_id", ""),
        "structural_path": chunk.get("structural_path", ""),
        "chunk_level": chunk.get("chunk_level", ""),
        "section_type_tags": chunk.get("section_type_tags", []),
        "rrf_score": chunk.get("rrf_score", 0.0),
        "char_start": chunk.get("char_start", 0),
        "char_end": chunk.get("char_end", 0),
    }
    return Document(page_content=text, metadata=metadata)


# ── Factory ───────────────────────────────────────────────────────────────────

def get_langchain_retriever(
    contract_id: str,
    tags: list[str] | None = None,
    levels: list[str] | None = None,
    top_k: int = 15,
) -> ContractHybridRetriever:
    """
    Factory that returns a contract-scoped LangChain retriever.

    Args:
        contract_id: The contract to search within.
        tags:        Section type tags / structural hints to prioritise.
        levels:      Chunk levels to include (macro / meso / micro).
        top_k:       Maximum documents to return per query.

    Returns:
        A ``ContractHybridRetriever`` ready for use in LangChain chains.
    """
    return ContractHybridRetriever(
        contract_id=contract_id,
        tags=tags,
        levels=levels,
        top_k=top_k,
    )


def get_voyage_embeddings() -> VoyageAILangChainEmbeddings:
    """
    Return a LangChain-compatible VoyageAI embeddings instance.

    Use this wherever LangChain expects an ``Embeddings`` object
    (e.g. ``MongoDBAtlasVectorSearch``, RAGAS evaluators, etc.)
    without importing any OpenAI dependency.
    """
    return VoyageAILangChainEmbeddings()
