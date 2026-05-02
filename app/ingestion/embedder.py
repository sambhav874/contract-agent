"""Voyage AI embedding service."""

import asyncio
import time
from typing import Literal

import voyageai

from app.config import settings
from app.db.models import ChunkDocument


class EmbeddingService:
    """Voyage AI embedding service with batching and retry logic."""

    def __init__(self):
        self.client = voyageai.Client(
            api_key=settings.voyage_api_key,
            base_url="https://ai.mongodb.com/v1"
        )
        self.model = settings.voyage_model
        self.batch_size = settings.chunk_batch_size
        self.max_retries = 3
        self.base_delay = 1.0  # seconds

    async def embed_documents(
        self,
        texts: list[str],
        input_type: Literal["document", "query"] = "document",
    ) -> list[list[float]]:
        """
        Embed a list of texts in batches.

        Args:
            texts: List of texts to embed
            input_type: 'document' for indexing, 'query' for retrieval

        Returns:
            List of embedding vectors
        """
        all_embeddings: list[list[float]] = []

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embeddings = await self._embed_batch(batch, input_type)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def _embed_batch(
        self,
        texts: list[str],
        input_type: Literal["document", "query"],
        retry_count: int = 0,
    ) -> list[list[float]]:
        """Embed a single batch with retry logic."""
        try:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self.client.embed(
                    texts,
                    model=self.model,
                    input_type=input_type,
                ).embeddings,
            )
            return embeddings

        except Exception as e:
            error_msg = str(e).lower()

            # Rate limit handling
            if "rate limit" in error_msg or "429" in error_msg:
                if retry_count < self.max_retries:
                    delay = self.base_delay * (2 ** retry_count)
                    await asyncio.sleep(delay)

                    # Reduce batch size on rate limit
                    if len(texts) > 32:
                        return await self._embed_with_reduced_batch(texts, input_type, retry_count + 1)

                    return await self._embed_batch(texts, input_type, retry_count + 1)

            raise

    async def _embed_with_reduced_batch(
        self,
        texts: list[str],
        input_type: Literal["document", "query"],
        retry_count: int,
    ) -> list[list[float]]:
        """Embed with reduced batch size after rate limit."""
        reduced_batch_size = min(32, len(texts))
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), reduced_batch_size):
            batch = texts[i:i + reduced_batch_size]
            batch_embeddings = await self._embed_batch(batch, input_type, retry_count)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query."""
        embeddings = await self.embed_documents([query], input_type="query")
        return embeddings[0]

    async def embed_chunks(self, chunks: list[ChunkDocument]) -> list[ChunkDocument]:
        """
        Embed a list of chunks and update their embedding field.

        Args:
            chunks: List of ChunkDocument objects

        Returns:
            Same list with embedding field populated
        """
        texts = [chunk.text for chunk in chunks]
        embeddings = await self.embed_documents(texts, input_type="document")

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        return chunks


# Global service instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def embed_text(text: str, input_type: Literal["document", "query"] = "document") -> list[float]:
    """Embed a single text."""
    service = get_embedding_service()
    return await service.embed_query(text) if input_type == "query" else (await service.embed_documents([text]))[0]


async def embed_query(query: str) -> list[float]:
    """Embed a query for retrieval."""
    service = get_embedding_service()
    return await service.embed_query(query)
