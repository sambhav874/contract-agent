"""Unit tests for IntentRouter — fallback, structural hints, and Gemini routing."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routing.intent_router import (
    route_intent,
    _route_fallback,
    _extract_structural_hints,
    _merge_unique,
)
from app.db.models import StructuralMap, StructuralSection


def _section(section_id="s1", title="Article IV: Payment", level=1, topic_tags=None):
    return StructuralSection(
        section_id=section_id,
        title=title,
        level=level,
        char_start=0,
        char_end=100,
        topic_tags=topic_tags or [],
    )


# ── _merge_unique ───────────────────────────────────────────────────────

def test_merge_unique():
    base = ["a", "b"]
    extra = ["b", "c", "a"]
    result = _merge_unique(base, extra)
    assert result == ["a", "b", "c"]


# ── _extract_structural_hints ─────────────────────────────────────────

class TestExtractStructuralHints:
    def test_no_map_returns_empty(self):
        assert _extract_structural_hints("risk", None) == []

    def test_risk_intent_keywords(self):
        s_map = StructuralMap(sections=[
            _section("1", "Section 1: Indemnification Clause"),
            _section("2", "Section 2: Payment Terms"),
        ])
        hints = _extract_structural_hints("RISK_ANALYSIS", s_map)
        assert len(hints) == 2
        assert "Indemnification" in hints[0]

    def test_kpi_intent_keywords(self):
        s_map = StructuralMap(sections=[
            _section("1", "Performance KPI"),
            _section("2", "General Provisions"),
        ])
        hints = _extract_structural_hints("KPI_QUERY", s_map)
        assert len(hints) == 1
        assert "Performance" in hints[0]

    def test_clause_intent_level(self):
        """clause intent includes all top-level sections."""
        s_map = StructuralMap(sections=[
            _section("1", "Top Section", level=1),
            _section("2", "Subsection", level=2),
        ])
        hints = _extract_structural_hints("CLAUSE_LOOKUP", s_map)
        assert hints == ["Top Section"]

    def test_topic_tags_matching(self):
        s_map = StructuralMap(sections=[
            _section("1", "Sec 1", topic_tags=["penalty"]),
            _section("2", "Sec 2", topic_tags=["unrelated"]),
        ])
        hints = _extract_structural_hints("KPI_QUERY", s_map)
        assert "Sec 1" in hints


# ── _route_fallback ──────────────────────────────────────────────────

def test_route_fallback():
    hints = ["Indemnification"]
    plan = _route_fallback("RISK_ANALYSIS", hints)
    assert plan.intent == "RISK_ANALYSIS"
    assert "Indemnification" in plan.priority_section_tags
    assert plan.output_schema_name == "RiskAnalysisOutput"
    assert plan.analysis_mode == "legal"


# ── route_intent ──────────────────────────────────────────────────────

class TestRouteIntent:
    @pytest.mark.asyncio
    async def test_route_intent_calls_gemini(self):
        s_map = StructuralMap(sections=[_section()])

        with patch("app.routing.intent_router.call_gemini", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "intent": "KPI_QUERY",
                "sub_intents": ["sla"],
                "priority_section_tags": ["Payment"],
                "chunk_levels": ["meso"],
                "map_pass_required": True,
                "max_retrieval_rounds": 4,
                "output_schema_name": "KPIExtractionOutput",
                "analysis_mode": "plain",
            }

            plan = await route_intent("KPI_QUERY", "Get KPI", s_map)

        assert plan.intent == "KPI_QUERY"
        assert "Payment" in plan.priority_section_tags
        assert plan.max_retrieval_rounds == 4

    @pytest.mark.asyncio
    async def test_route_intent_fallback_on_error(self):
        s_map = StructuralMap(sections=[_section(title="Indemnification")])

        with patch("app.routing.intent_router.call_gemini", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = RuntimeError("Gemini down")
            # Should seamlessly fall back to hardcoded plan
            plan = await route_intent("RISK_ANALYSIS", "Get Risk", s_map)

        assert plan.intent == "RISK_ANALYSIS"
        assert "Indemnification" in plan.priority_section_tags
