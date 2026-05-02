"""Markdown structural parser and metadata extractor."""

import re
from typing import Any

from app.db.models import ContractMetadata, StructuralMap, StructuralSection


# Legal section patterns
SECTION_PATTERNS = [
    r"^(Article\s+\d+[.:-]?\s*)",  # Article 1, Article 1.
    r"^(Section\s+\d+[.\d]*\s*)",  # Section 1.1, Section 1.1.1
    r"^(Clause\s+\d+[.:-]?\s*)",  # Clause 1, Clause 1.1
    r"^(Part\s+[IVX]+[.:-]?\s*)",  # Part I, Part IV
    r"^(Schedule\s+[A-Z][.:-]?\s*)",  # Schedule A, Schedule 1
    r"^(Annex\s+[A-Z\d]+[.:-]?\s*)",  # Annex A, Annex 1
    r"^(Exhibit\s+[A-Z\d]+[.:-]?\s*)",  # Exhibit A, Exhibit 1
    r"^(Appendix\s+[A-Z\d]+[.:-]?\s*)",  # Appendix A
]

# Section type tag mappings
SECTION_TAG_KEYWORDS = {
    "indemnification": ["indemnif", "hold harmless"],
    "liability": ["liability", "limitation of liability", "damages"],
    "warranty": ["warranty", "warrant", "guarantee"],
    "representation": ["representation", "represent"],
    "termination": ["termination", "terminate", "expiry"],
    "dispute_resolution": ["dispute", "arbitration", "mediation", "litigation"],
    "force_majeure": ["force majeure", "act of god", "unforeseen"],
    "ip_ownership": ["intellectual property", "ip", "patent", "trademark", "copyright"],
    "confidentiality": ["confidential", "non-disclosure", "nda"],
    "payment": ["payment", "fee", "price", "invoice", "billing"],
    "milestone": ["milestone", "deliverable", "completion"],
    "sla": ["sla", "service level", "uptime", "availability"],
    "penalty": ["penalty", "late fee", "liquidated damages"],
    "governing_law": ["governing law", "choice of law", "jurisdiction"],
    "definitions": ["definition", "defined terms"],
    "recitals": ["recital", "whereas", "background"],
    "covenants": ["covenant", "agree to", "undertake"],
    "assignment": ["assignment", "assign", "transfer"],
    "notice": ["notice", "notification"],
    "schedule": ["schedule", "attachment"],
    "annex": ["annex", "appendix"],
}


def clean_liteparse_artefacts(text: str) -> str:
    """Remove LiteParse artefacts: page numbers, headers, watermarks."""
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        # Skip page number patterns (standalone digits)
        if re.match(r"^\s*\d+\s*$", line):
            continue
        # Skip watermark patterns
        if re.search(r"(liteparse|llamaindex|parsed by)", line, re.IGNORECASE):
            continue
        # Skip "Page N" lines
        if re.match(r"^Page\s+\d+$", line.strip(), re.IGNORECASE):
            continue
        cleaned.append(line)

    return "\n".join(cleaned)


def detect_heading_level(line: str) -> int:
    """Detect Markdown heading level (1-6)."""
    match = re.match(r"^(#{1,6})\s+", line)
    if match:
        return len(match.group(1))
    return 0


def detect_legal_section(line: str) -> tuple[str | None, int]:
    """
    Detect legal section patterns and return (section_text, level).
    Level: 0=Article/Part, 1=Section, 2=Subsection
    """
    stripped = line.strip()

    # Article or Part (top level)
    if re.match(r"^Article\s+\d+", stripped, re.IGNORECASE):
        return stripped, 0
    if re.match(r"^Part\s+[IVX]+", stripped, re.IGNORECASE):
        return stripped, 0
    if re.match(r"^Part\s+\d+", stripped, re.IGNORECASE):
        return stripped, 0

    # Section (mid level) - including "Section X.XX" patterns
    if re.match(r"^Section\s+\d+[\.\d]*", stripped, re.IGNORECASE):
        return stripped, 1

    # Clause (can be mid or low)
    if re.match(r"^Clause\s+\d+", stripped, re.IGNORECASE):
        return stripped, 2

    # Schedule/Exhibit/Annex
    if re.match(r"^(Schedule|Exhibit|Annex|Appendix)\s+[A-Z\d]", stripped, re.IGNORECASE):
        return stripped, 0

    return None, -1


def extract_definitions_section(text: str) -> dict[str, str]:
    """Extract definitions from a Definitions section."""
    definitions = {}

    # Look for "Definitions" section
    def_pattern = r"^(#+)\s*Definitions?[:\s]*"
    match = re.search(def_pattern, text, re.IGNORECASE | re.MULTILINE)

    if match:
        # Find the section content
        start = match.end()
        # Look for next heading or end
        next_heading = re.search(r"\n#{1,3}\s+", text[start:])
        section_text = text[start:start + next_heading.start()] if next_heading else text[start:]

        # Extract "Term" means "Definition" patterns
        term_patterns = [
            r'"([^"]+)"\s*(?:means|refers to|shall mean)?\s*([^.]+)',
            r"\"([^\"]+)\"\s*is\s*(.+?)(?:\.|$)",
        ]

        for pattern in term_patterns:
            for m in re.finditer(pattern, section_text, re.IGNORECASE):
                term = m.group(1).strip()
                definition = m.group(2).strip().rstrip(".,;")
                definitions[term] = definition

    return definitions


def assign_section_tags(title: str, content: str = "") -> list[str]:
    """Assign section type tags based on title and content."""
    tags = []
    title_lower = title.lower()
    content_lower = content.lower()[:500]  # First 500 chars
    combined = f"{title_lower} {content_lower}"

    for tag, keywords in SECTION_TAG_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined:
                tags.append(tag)
                break

    return tags


def parse_markdown(text: str, contract_id: str) -> tuple[StructuralMap, dict[str, Any]]:
    """
    Parse Markdown text and extract structural map.

    Returns:
        Tuple of (StructuralMap, metadata_dict)
    """
    text = clean_liteparse_artefacts(text)
    lines = text.split("\n")

    sections: list[StructuralSection] = []
    current_section_stack: list[tuple[str, int]] = []  # (section_id, level)
    char_pos = 0

    # Track current position
    current_heading: dict[str, Any] = {
        "title": "",
        "level": 0,
        "start": 0,
    }

    # First pass: identify all sections
    section_starts: list[tuple[int, str, int]] = []  # (char_start, title, level)

    for i, line in enumerate(lines):
        char_pos_start = char_pos
        stripped = line.strip()

        # Check for Markdown heading
        heading_level = detect_heading_level(stripped)
        if heading_level > 0:
            title = stripped.lstrip("#").strip()
            section_starts.append((char_pos_start, title, heading_level))

        char_pos += len(line) + 1  # +1 for newline

    # Check for legal section patterns
    char_pos = 0
    legal_sections: list[tuple[int, str, int]] = []  # (char_start, title, inferred_level)

    for line in lines:
        stripped = line.strip()
        section_text, level = detect_legal_section(stripped)
        if section_text:
            legal_sections.append((char_pos, section_text, level))
        char_pos += len(line) + 1

    # Merge and sort sections
    all_sections = section_starts + legal_sections
    all_sections.sort(key=lambda x: x[0])

    # Remove duplicates (same char position)
    seen_positions = set()
    merged_sections: list[tuple[int, str, int]] = []
    for pos, title, level in all_sections:
        if pos not in seen_positions:
            merged_sections.append((pos, title, level))
            seen_positions.add(pos)

    # Build structural map
    parent_stack: list[tuple[str, int, int]] = []  # (section_id, level, char_start)

    for i, (char_start, title, level) in enumerate(merged_sections):
        # Determine end position
        if i + 1 < len(merged_sections):
            char_end = merged_sections[i + 1][0]
        else:
            char_end = len(text)

        section_id = f"section_{char_start}_{char_end}"
        section_title = title.rstrip("#").strip()

        # Find parent
        parent_id = None
        while parent_stack and parent_stack[-1][1] >= level:
            parent_stack.pop()

        if parent_stack:
            parent_id = parent_stack[-1][0]

        parent_stack.append((section_id, level, char_start))

        # Assign tags
        section_text = text[char_start:char_end] if char_end <= len(text) else text[char_start:]
        tags = assign_section_tags(section_title, section_text)

        section = StructuralSection(
            section_id=section_id,
            title=section_title,
            level=level,
            char_start=char_start,
            char_end=char_end,
            parent_id=parent_id,
            topic_tags=tags,
        )
        sections.append(section)

    structural_map = StructuralMap(sections=sections)

    # Extract metadata from first 4000 chars
    metadata = extract_metadata(text[:4000], contract_id)

    return structural_map, metadata


def extract_metadata(text: str, contract_id: str) -> dict[str, Any]:
    """Extract metadata from contract text."""
    metadata: dict[str, Any] = {
        "contract_id": contract_id,
        "name": "Unknown",
    }

    # Look for party patterns
    party_patterns = [
        r'between\s+([^.]+?)\s+and\s+([^.]+)',
        r'(?:party|parties)\s*:\s*([^.]+)',
    ]

    for pattern in party_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata["parties_raw"] = match.group(0).strip()
            break

    # Look for governing law
    law_match = re.search(r"governing law[:\s]*([^\n]+)", text, re.IGNORECASE)
    if law_match:
        metadata["governing_law"] = law_match.group(1).strip()

    # Look for effective date
    date_match = re.search(r"(?:effective|commencement|date)[:\s]*(\w+\s+\d+,\s*\d+)", text, re.IGNORECASE)
    if date_match:
        metadata["effective_date"] = date_match.group(1).strip()

    return metadata


async def parse_contract(file_path: str, name: str | None = None) -> tuple[ContractMetadata, StructuralMap]:
    """
    Parse a contract Markdown file.

    Args:
        file_path: Path to the .md file
        name: Optional name for the contract

    Returns:
        Tuple of (ContractMetadata, StructuralMap)
    """
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    contract_id = name.lower().replace(" ", "_").replace("-", "_") if name else None
    structural_map, metadata_dict = parse_markdown(text, contract_id or "")

    # Create metadata object
    contract_metadata = ContractMetadata(
        contract_id=metadata_dict.get("contract_id", contract_id) or str(id(text)),
        name=name or "Unknown Contract",
        governing_law=metadata_dict.get("governing_law"),
        effective_date=metadata_dict.get("effective_date"),
        structural_map=structural_map.model_dump(),
    )

    return contract_metadata, structural_map
