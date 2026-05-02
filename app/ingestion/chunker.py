"""Hierarchical chunker for contract text."""

import re
from typing import Any

import tiktoken

from app.db.models import ChunkDocument, StructuralMap
from app.ingestion.parser import assign_section_tags

# Token encoder
ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text."""
    return len(ENCODER.encode(text))


def hierarchical_chunk(
    text: str,
    contract_id: str,
    structural_map: StructuralMap,
    macro_tokens: tuple[int, int] = (2000, 4000),
    meso_tokens: tuple[int, int] = (400, 700),
    micro_tokens: tuple[int, int] = (80, 150),
) -> list[ChunkDocument]:
    """
    Create hierarchical chunks at three levels.

    Strategy:
    1. MACRO: One chunk per top-level section (level 0-1 in hierarchy)
    2. MESO: One chunk per subsection (level 2+) OR split large sections
    3. MICRO: Extract specific values from meso chunks

    Args:
        text: Full contract text
        contract_id: Contract identifier
        structural_map: Parsed structural map
        macro_tokens: (min, max) tokens for macro chunks
        meso_tokens: (min, max) tokens for meso chunks
        micro_tokens: (min, max) tokens for micro chunks

    Returns:
        List of ChunkDocument objects at all levels
    """
    chunks: list[ChunkDocument] = []
    sections = structural_map.sections

    if not sections:
        # Fallback: create single chunk
        chunk = create_chunk(
            text=text,
            contract_id=contract_id,
            level="macro",
            char_start=0,
            char_end=len(text),
            title="Full Contract",
        )
        chunks.append(chunk)
        return chunks

    # Group sections by hierarchy level
    # Level 0-1 = macro, Level 2+ = meso
    max_heading_depth = max((s.level for s in sections), default=0)

    for section in sections:
        # MACRO: Top-level headers (Articles, Parts, Exhibits)
        # Usually level 0 or 1, but we'll take anything that's a root or near-root
        is_macro = section.level <= 2 or section.parent_id is None
        
        if is_macro:
            chunk_level = "macro"
        else:
            chunk_level = "meso"

        # Create the chunk
        main_chunk = create_chunk(
            text=text,
            contract_id=contract_id,
            level=chunk_level,
            char_start=section.char_start,
            char_end=section.char_end,
            title=section.title,
            parent_id=section.parent_id,
        )
        chunks.append(main_chunk)

        # If it's a large macro/meso chunk, we might want to split it further
        # but for now, the parser already split the text into sections.
        # However, if a section is very large (> 4000 tokens), we should split it.
        section_text = text[section.char_start:section.char_end]
        section_tokens = count_tokens(section_text)
        
        if section_tokens > macro_tokens[1]:
            # This is a massive section, split into meso parts
            meso_parts = split_section_to_meso(
                text=text,
                contract_id=contract_id,
                section=section,
                target_max=meso_tokens[1],
            )
            for m in meso_parts:
                m.parent_chunk_id = main_chunk.chunk_id
                main_chunk.child_chunk_ids.append(m.chunk_id)
                chunks.append(m)

        # Create micro chunks for all sections
        section_text = text[section.char_start:section.char_end]
        micro_chunks = create_micro_chunks(
            text=text,
            contract_id=contract_id,
            char_start=section.char_start,
            section_text=section_text,
            target_min=micro_tokens[0],
            target_max=micro_tokens[1],
        )
        chunks.extend(micro_chunks)

    return chunks


def split_section_to_meso(
    text: str,
    contract_id: str,
    section: Any,
    target_max: int,
) -> list[ChunkDocument]:
    """Split a large section into meso chunks."""
    chunks: list[ChunkDocument] = []
    section_text = text[section.char_start:section.char_end]

    # Try to split by subsections first
    subsections = find_subsections(section_text)

    if subsections and len(subsections) > 1:
        # Use natural subsection boundaries
        for start, title in subsections:
            # Find end position
            idx = subsections.index((start, title))
            if idx + 1 < len(subsections):
                end = subsections[idx + 1][0]
            else:
                end = len(section_text)

            sub_text = section_text[start:end]
            token_count = count_tokens(sub_text)

            if token_count > 0:
                chunk = ChunkDocument(
                    chunk_id=f"{contract_id}_meso_{section.section_id}_{start}",
                    contract_id=contract_id,
                    chunk_level="meso",
                    text=sub_text,
                    token_count=token_count,
                    structural_path=f"{section.title} > {title}",
                    section_type_tags=assign_section_tags(title, sub_text),
                    char_start=section.char_start + start,
                    char_end=section.char_start + start + len(sub_text),
                    parent_chunk_id=None,
                )
                chunks.append(chunk)
    else:
        # Fall back to sentence-based splitting
        sentences = re.split(r"(?<=[.!?])\s+", section_text)
        current_chunk: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = count_tokens(sentence)

            if current_tokens + sentence_tokens > target_max and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunk = create_chunk(
                    text=text,
                    contract_id=contract_id,
                    level="meso",
                    char_start=section.char_start,
                    char_end=section.char_start + len(chunk_text),
                    title=f"{section.title} (part)",
                    parent_id=section.section_id,
                )
                chunks.append(chunk)
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunk = create_chunk(
                text=text,
                contract_id=contract_id,
                level="meso",
                char_start=section.char_start,
                char_end=section.char_end,
                title=f"{section.title} (continued)",
                parent_id=section.section_id,
            )
            chunks.append(chunk)

    return chunks


def find_subsections(text: str) -> list[tuple[int, str]]:
    """Find subsection boundaries in text."""
    subsections = []
    lines = text.split('\n')
    char_pos = 0

    for line in lines:
        stripped = line.strip()
        # Look for ### or #### headings
        if re.match(r'^#{3,4}\s+', stripped):
            title = re.sub(r'^#{3,4}\s+', '', stripped)
            subsections.append((char_pos, title))
        # Look for Section X.X patterns
        elif re.match(r'^(Section\s+\d+\.\d+|Article\s+\d+|[IVX]+\.\s*\d+)', stripped):
            match = re.match(r'^([^:]+):?', stripped)
            if match:
                subsections.append((char_pos, match.group(1)))
        char_pos += len(line) + 1

    return subsections


def create_chunk(
    text: str,
    contract_id: str,
    level: str,
    char_start: int,
    char_end: int,
    title: str,
    parent_id: str | None = None,
) -> ChunkDocument:
    """Create a single chunk document."""
    chunk_text = text[char_start:char_end]
    token_count = count_tokens(chunk_text)

    # Build structural path
    structural_path = title

    # Assign section type tags
    tags = assign_section_tags(title, chunk_text)

    return ChunkDocument(
        contract_id=contract_id,
        chunk_level=level,
        text=chunk_text,
        token_count=token_count,
        structural_path=structural_path,
        section_type_tags=tags,
        char_start=char_start,
        char_end=char_end,
        parent_chunk_id=parent_id,
    )


def create_micro_chunks(
    text: str,
    contract_id: str,
    char_start: int,
    section_text: str,
    target_min: int,
    target_max: int,
) -> list[ChunkDocument]:
    """Create micro-level chunks for specific values."""
    chunks: list[ChunkDocument] = []

    # Patterns for specific values
    value_patterns = [
        (r"\$[\d,]+(?:\.\d+)?", "monetary"),
        (r"\d+(?:\.\d+)?\s*(?:days?|weeks?|months?|years?)", "duration"),
        (r"\d+(?:\.\d+)?%", "percentage"),
        (r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s*\d+", "date"),
        (r"\d+\.\d+%", "percentage"),
        (r">\s*\d+\.?\d*\s*%", "threshold"),
        (r"\d+\.?\d*\s*(?:hours?|minutes?|seconds?)", "time"),
    ]

    for pattern, value_type in value_patterns:
        matches = list(re.finditer(pattern, section_text, re.IGNORECASE))

        for match in matches:
            start = match.start()
            end = match.end()

            # Find context around the value (sentence boundaries)
            context_start = max(0, section_text.rfind('.', 0, start))
            if context_start == 0 and start > 50:
                context_start = max(0, start - 80)
            elif context_start > 0:
                context_start += 1  # Skip the period

            context_end = section_text.find('.', end)
            if context_end == -1:
                context_end = min(len(section_text), end + 80)
            else:
                context_end = min(len(section_text), context_end + 1)

            micro_text = section_text[context_start:context_end].strip()
            token_count = count_tokens(micro_text)

            if 10 <= token_count <= 200:  # Reasonable micro chunk
                chunk = ChunkDocument(
                    chunk_id=f"{contract_id}_micro_{char_start}_{start}",
                    contract_id=contract_id,
                    chunk_level="micro",
                    text=micro_text,
                    token_count=token_count,
                    structural_path=f"Value: {match.group()}",
                    section_type_tags=[value_type],
                    char_start=char_start + context_start,
                    char_end=char_start + context_end,
                    parent_chunk_id=None,
                )
                chunks.append(chunk)

    return chunks


def format_chunk_for_retrieval(chunk: ChunkDocument) -> str:
    """Format a chunk for retrieval display."""
    return f"""[CHUNK_ID: {chunk.chunk_id}]
[PATH: {chunk.structural_path}]
[CHAR_RANGE: {chunk.char_start}-{chunk.char_end}]
[LEVEL: {chunk.chunk_level}]
[TAGS: {', '.join(chunk.section_type_tags) or 'none'}]
{chunk.text}
---
"""
