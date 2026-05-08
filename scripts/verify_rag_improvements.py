"""Quick verification script for new RAG improvements."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.chunker import split_section_to_meso

CONTRACT_ID = "test_contract_001"

# Mock section for chunking test
class MockSection:
    section_id = "sec_001"
    title = "Article I. Definitions"
    char_start = 0
    char_end = 5000
    level = 1
    parent_id = None


def test_chunk_overlap():
    print("=== Chunk Overlap ===")
    big_text = "This is sentence one. " * 20 + "This is sentence two. " * 20 + \
               "This is sentence three. " * 20 + "This is sentence four. " * 20 + \
               "This is sentence five. " * 20
    section = MockSection()
    chunks = split_section_to_meso(big_text, CONTRACT_ID, section, target_max=80)
    print(f"Produced {len(chunks)} meso chunks")
    for i, c in enumerate(chunks):
        print(f"  {i}: {c.char_start}-{c.char_end} | parent={c.parent_chunk_id} | len={len(c.text)}")
    print()


if __name__ == "__main__":
    test_chunk_overlap()
