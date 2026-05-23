"""Tests for MongoDB retrieval."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_retriever_import():
    """Test that retriever module imports correctly."""
    from app.retrieval.retriever import Retriever, get_retriever, format_chunks_for_context
    assert Retriever is not None
    assert callable(get_retriever)
    assert callable(format_chunks_for_context)


def test_format_chunks_for_context():
    """Test formatting of chunks for LLM context."""
    from app.retrieval.retriever import format_chunks_for_context

    chunks = [
        {
            "chunk_id": "chunk_1",
            "structural_path": "Article 1 > Section 1.1",
            "char_start": 0,
            "char_end": 100,
            "chunk_level": "meso",
            "section_type_tags": ["confidentiality"],
            "text": "This is confidential information."
        }
    ]

    formatted = format_chunks_for_context(chunks)

    assert "chunk_1" in formatted
    assert "Article 1 > Section 1.1" in formatted
    assert "confidentiality" in formatted
    assert "This is confidential information." in formatted


@pytest.mark.asyncio
async def test_retriever_fetch_structure():
    """Test that retriever can be instantiated and has correct structure."""
    from app.retrieval.retriever import Retriever

    retriever = Retriever()
    assert retriever.vector_index == "chunk_embedding_index"
    assert hasattr(retriever, "fetch")
    assert hasattr(retriever, "fetch_by_section")


def test_mongodb_connection_structure():
    """Test MongoDB connection module structure."""
    from app.db.mongodb import MongoDB

    assert hasattr(MongoDB, "connect")
    assert hasattr(MongoDB, "disconnect")
    assert hasattr(MongoDB, "get_collection")
    assert hasattr(MongoDB, "insert_contract")
    assert hasattr(MongoDB, "get_contract")


def test_models_structure():
    """Test that Pydantic models are correctly structured."""
    from app.db.models import (
        ContractMetadata, ChunkDocument, AnalysisJob,
        RiskAnalysisOutput, KPIExtractionOutput, ClauseAnalysisOutput,
        ObligationTrackingOutput, SummaryOutput, RedFlagOutput
    )

    # Test instantiation
    metadata = ContractMetadata(name="Test Contract")
    assert metadata.name == "Test Contract"
    assert metadata.contract_id is not None

    # Test chunk document
    chunk = ChunkDocument(
        contract_id="test",
        chunk_level="macro",
        text="Test text",
        token_count=10,
        structural_path="Test",
        char_start=0,
        char_end=10
    )
    assert chunk.chunk_id is not None
    assert chunk.chunk_level == "macro"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
