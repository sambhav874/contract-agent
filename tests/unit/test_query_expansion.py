"""Unit tests for query expansion and intent classification."""

import pytest
from unittest.mock import AsyncMock, patch


# ── query_expansion ───────────────────────────────────────────────────

class TestExpandQuery:
    @pytest.mark.asyncio
    async def test_expand_returns_structured_response(self):
        from app.retrieval.query_expansion import expand_query

        with patch("app.retrieval.query_expansion.call_gemini", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "original_query": "termination clause",
                "expanded_query": "termination provisions cancellation rights exit clause",
                "search_variants": ["termination", "contract termination"],
                "key_terms": ["termination", "exit"],
            }
            result = await expand_query("termination clause")

        assert result["original_query"] == "termination clause"
        assert "expanded_query" in result
        assert isinstance(result["search_variants"], list)
        assert isinstance(result["key_terms"], list)

    @pytest.mark.asyncio
    async def test_expand_fail_open_on_error(self):
        from app.retrieval.query_expansion import expand_query

        with patch("app.retrieval.query_expansion.call_gemini", new_callable=AsyncMock) as mock:
            mock.side_effect = RuntimeError("API failure")
            result = await expand_query("indemnification clause")

        # Should not raise; returns identity result
        assert result["original_query"] == "indemnification clause"
        assert result["expanded_query"] == "indemnification clause"
        # Fail-open returns the full query string as single search variant
        assert "indemnification clause" in result["search_variants"]

    @pytest.mark.asyncio
    async def test_expand_overrides_original_query(self):
        """Even if LLM returns a different original_query, we override it."""
        from app.retrieval.query_expansion import expand_query

        with patch("app.retrieval.query_expansion.call_gemini", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "original_query": "WRONG",
                "expanded_query": "liability limitations cap indemnification",
                "search_variants": ["liability cap"],
                "key_terms": ["liability"],
            }
            result = await expand_query("liability limit")

        assert result["original_query"] == "liability limit"
