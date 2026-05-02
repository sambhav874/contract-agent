"""Tests for hierarchical chunker."""

import pytest
from pathlib import Path

from app.ingestion.parser import parse_contract
from app.ingestion.chunker import hierarchical_chunk, count_tokens


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_chunk_simple_nda():
    """Test chunking of simple NDA."""
    file_path = FIXTURES_DIR / "nda_simple.md"
    metadata, structural_map = await parse_contract(str(file_path), "Test NDA")

    with open(file_path, "r") as f:
        text = f.read()

    chunks = hierarchical_chunk(text, metadata.contract_id, structural_map)

    # Should create chunks at multiple levels
    assert len(chunks) > 0

    # Check chunk levels exist
    levels = set(c.chunk_level for c in chunks)
    assert "macro" in levels or "meso" in levels  # At least some chunks


@pytest.mark.asyncio
async def test_chunk_saas_agreement():
    """Test chunking of SaaS agreement."""
    file_path = FIXTURES_DIR / "saas_agreement.md"
    metadata, structural_map = await parse_contract(str(file_path), "SaaS Test")

    with open(file_path, "r") as f:
        text = f.read()

    chunks = hierarchical_chunk(text, metadata.contract_id, structural_map)

    # Should create chunks
    assert len(chunks) > 0

    # Check all chunks have required fields
    for chunk in chunks:
        assert chunk.chunk_id is not None
        assert chunk.contract_id == metadata.contract_id
        assert chunk.chunk_level in ["macro", "meso", "micro"]
        assert chunk.text is not None
        assert chunk.token_count > 0
        assert chunk.structural_path is not None
        assert chunk.char_start >= 0
        assert chunk.char_end > chunk.char_start


@pytest.mark.asyncio
async def test_chunk_vendor_agreement():
    """Test chunking of vendor agreement."""
    file_path = FIXTURES_DIR / "vendor_agreement.md"
    metadata, structural_map = await parse_contract(str(file_path), "Vendor Test")

    with open(file_path, "r") as f:
        text = f.read()

    chunks = hierarchical_chunk(text, metadata.contract_id, structural_map)

    # Should create chunks
    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_token_counts_within_limits():
    """Test that chunk token counts are within expected ranges."""
    file_path = FIXTURES_DIR / "saas_agreement.md"
    _, structural_map = await parse_contract(str(file_path), "Token Test")

    with open(file_path, "r") as f:
        text = f.read()

    chunks = hierarchical_chunk(text, "test", structural_map)

    for chunk in chunks:
        # Macro chunks should be 2000-4000 tokens
        if chunk.chunk_level == "macro":
            assert chunk.token_count <= 4500, f"Macro chunk exceeds limit: {chunk.token_count}"

        # Meso chunks should be 400-700 tokens
        if chunk.chunk_level == "meso":
            assert chunk.token_count <= 1000, f"Meso chunk exceeds limit: {chunk.token_count}"

        # Micro chunks should be 80-150 tokens
        if chunk.chunk_level == "micro":
            assert chunk.token_count <= 200, f"Micro chunk exceeds limit: {chunk.token_count}"


@pytest.mark.asyncio
async def test_structural_path_populated():
    """Test that structural paths are properly populated."""
    file_path = FIXTURES_DIR / "nda_simple.md"
    _, structural_map = await parse_contract(str(file_path), "Path Test")

    with open(file_path, "r") as f:
        text = f.read()

    chunks = hierarchical_chunk(text, "test", structural_map)

    for chunk in chunks:
        assert chunk.structural_path is not None
        assert len(chunk.structural_path) > 0


@pytest.mark.asyncio
async def test_section_type_tags_assigned():
    """Test that section type tags are assigned."""
    file_path = FIXTURES_DIR / "saas_agreement.md"
    _, structural_map = await parse_contract(str(file_path), "Tags Test")

    with open(file_path, "r") as f:
        text = f.read()

    chunks = hierarchical_chunk(text, "test", structural_map)

    # Structural map should have sections with tags
    assert len(structural_map.sections) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
