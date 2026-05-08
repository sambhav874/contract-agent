"""Query expansion via lightweight LLM call before embedding."""

import asyncio
import json

from app.config import settings
from app.llm.gemini_client import call_gemini


EXPANSION_SYSTEM_PROMPT = """You are a legal query expansion assistant.
Given a natural language query about a contract, produce an expanded version
optimized for semantic + lexical retrieval. Rules:
1. Expand abbreviations and acronyms
2. Normalize legal synonyms (e.g., indemnify → indemnification, hold harmless, defend)
3. Add contextual terms that keyword search would need
4. Return ONLY valid JSON with the original and expanded fields.
"""

_EXPANSION_SCHEMA = {
    "type": "object",
    "properties": {
        "original_query": {"type": "string"},
        "expanded_query": {"type": "string"},
        "search_variants": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Alternative phrasings to increase recall"
        },
        "key_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Extracted keywords for lexical boost"
        },
    },
    "required": ["original_query", "expanded_query", "search_variants", "key_terms"],
}


async def expand_query(query: str) -> dict:
    """
    Expand a user query using Gemini Flash.

    Returns a dict with:
        original_query, expanded_query, search_variants, key_terms
    """
    try:
        response = await call_gemini(
            model=settings.gemini_fast_model,
            system_prompt=EXPANSION_SYSTEM_PROMPT,
            user_message=f"Expand this contract query:\n\n{query}",
            response_schema=_EXPANSION_SCHEMA,
            temperature=0.0,
        )
        response["original_query"] = query
        return response
    except Exception:
        # Fail open: return identity result on any error
        return {
            "original_query": query,
            "expanded_query": query,
            "search_variants": [query],
            "key_terms": query.split(),
        }
