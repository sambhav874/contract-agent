"""Tests for Markdown parser."""

import pytest
from pathlib import Path

from app.ingestion.parser import parse_contract, clean_liteparse_artefacts, detect_legal_section


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "contracts"


def test_clean_liteparse_artefacts():
    """Test cleaning of LiteParse artefacts."""
    text = """
# Contract

Some content here.
More content.

Powered by LiteParse
"""
    cleaned = clean_liteparse_artefacts(text)
    assert "LiteParse" not in cleaned
    assert "Some content here" in cleaned


def test_detect_legal_section():
    """Test legal section pattern detection."""
    test_cases = [
        ("Article 1: Definitions", True, 0),
        ("Section 1.1 Confidential Information", True, 1),
        ("Clause 3.2 Payment Terms", True, 2),
        ("Schedule A - Fees", True, 0),
        ("Part I - General", True, 0),
        ("Regular text", False, -1),
    ]

    for text, should_match, expected_level in test_cases:
        result, level = detect_legal_section(text)
        if should_match:
            assert result is not None
            assert level == expected_level
        else:
            assert result is None


@pytest.mark.asyncio
async def test_parse_simple_nda():
    """Test parsing of simple NDA contract."""
    file_path = FIXTURES_DIR / "nda_simple.md"
    metadata, structural_map, _ = await parse_contract(str(file_path), "Test NDA")

    # Check metadata
    assert metadata.name == "Test NDA"
    assert metadata.contract_id is not None

    # Check structural map has sections
    assert len(structural_map.sections) > 0

    # Should detect key sections
    section_titles = [s.title for s in structural_map.sections]
    expected_sections = ["DEFINITIONS", "OBLIGATIONS", "TERM AND TERMINATION", "REMEDIES", "GENERAL PROVISIONS"]

    for expected in expected_sections:
        assert any(expected.lower() in title.lower() for title in section_titles), \
            f"Missing section: {expected}"


@pytest.mark.asyncio
async def test_parse_saas_agreement():
    """Test parsing of SaaS agreement."""
    file_path = FIXTURES_DIR / "saas_agreement.md"
    metadata, structural_map, _ = await parse_contract(str(file_path), "SaaS Test")

    assert metadata.name == "SaaS Test"
    assert len(structural_map.sections) > 0

    # Check for key SaaS sections
    section_titles = [s.title for s in structural_map.sections]
    expected = ["DEFINITIONS", "SUBSCRIPTION AND ACCESS", "SERVICE LEVEL AGREEMENT",
                "FEES AND PAYMENT", "DATA SECURITY", "INTELLECTUAL PROPERTY"]

    for exp in expected:
        assert any(exp.lower() in title.lower() for title in section_titles)


@pytest.mark.asyncio
async def test_parse_vendor_agreement():
    """Test parsing of vendor agreement."""
    file_path = FIXTURES_DIR / "vendor_agreement.md"
    metadata, structural_map, _ = await parse_contract(str(file_path), "Vendor Test")

    assert metadata.name == "Vendor Test"
    assert len(structural_map.sections) > 3  # Should have multiple sections

    # Check section hierarchy
    sections = structural_map.sections
    assert len(sections) > 0

    # Check char offsets are valid
    for section in sections:
        assert section.char_start >= 0
        assert section.char_end > section.char_start
        assert section.level >= 0


@pytest.mark.asyncio
async def test_section_tag_assignment():
    """Test that sections are assigned appropriate tags."""
    file_path = FIXTURES_DIR / "nda_simple.md"
    _, structural_map, _ = await parse_contract(str(file_path), "Tag Test")

    # Should have tags assigned
    for section in structural_map.sections:
        # Tags should be a list
        assert isinstance(section.topic_tags, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
