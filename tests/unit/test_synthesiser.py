"""Unit tests for Synthesiser — narrative generation, stats computation."""

import pytest
from unittest.mock import AsyncMock, patch

from app.synthesis.synthesiser import Synthesiser, synthesise_output
from app.db.models import (
    RiskAnalysisOutput, RiskItem,
    KPIExtractionOutput, KPIItem,
    RedFlagOutput, RedFlag,
    BaseAnalysisOutput,
)


def _risk_item(severity=3):
    return RiskItem(
        severity=severity, risk_type="financial", exposed_party="Buyer",
        section="Section 5", structural_path="Article V > Section 5",
        clause_text="Indemnify for all losses", explanation="High exposure",
        mitigation_suggestion="Cap liability", confidence=0.9,
    )


# ── Narrative generation ──────────────────────────────────────────────

class TestSynthesiserNarrative:
    @pytest.mark.asyncio
    async def test_synthesise_returns_keys(self):
        synth = Synthesiser()
        output = BaseAnalysisOutput()

        with patch("app.synthesis.synthesiser.call_gemini", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = {"summary": "All good."}
            result = await synth.synthesise(output, mode="plain")

        assert "structured" in result
        assert "narrative" in result
        assert "statistics" in result
        assert result["narrative"] == "All good."

    @pytest.mark.asyncio
    async def test_narrative_fallback_on_gemini_error(self):
        synth = Synthesiser()
        output = BaseAnalysisOutput()

        with patch("app.synthesis.synthesiser.call_gemini", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.side_effect = RuntimeError("API down")
            result = await synth.synthesise(output, mode="plain")

        # Fallback: does not raise, returns type name
        assert "BaseAnalysisOutput" in result["narrative"]

    @pytest.mark.asyncio
    async def test_narrative_uses_text_key_fallback(self):
        synth = Synthesiser()
        output = BaseAnalysisOutput()

        with patch("app.synthesis.synthesiser.call_gemini", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = {"text": "Contract looks good."}
            result = await synth.synthesise(output)

        assert result["narrative"] == "Contract looks good."

    @pytest.mark.asyncio
    async def test_legal_mode_prompt(self):
        synth = Synthesiser()
        output = BaseAnalysisOutput()
        captured_prompts = []

        async def capture_call(**kwargs):
            captured_prompts.append(kwargs.get("system_prompt", ""))
            return {"summary": "Legal analysis done."}

        with patch("app.synthesis.synthesiser.call_gemini", side_effect=capture_call):
            await synth.synthesise(output, mode="legal")

        assert "legal terminology" in captured_prompts[0]


# ── Stats computation ─────────────────────────────────────────────────

class TestSynthesiserStats:
    def test_risk_stats(self):
        synth = Synthesiser()
        output = RiskAnalysisOutput(
            overall_risk_score=7.2,
            risk_grade="C",
            risks=[_risk_item(3), _risk_item(5), _risk_item(3)],
        )
        stats = synth._compute_stats(output)
        assert stats["total_risks"] == 3
        assert stats["by_severity"]["3"] == 2
        assert stats["by_severity"]["5"] == 1

    def test_kpi_stats(self):
        synth = Synthesiser()
        kpi = KPIItem(
            name="Delivery Rate", value="95", unit="%",
            kpi_type="sla", party="Supplier",
            trigger_condition="Below 95%",
            section="Schedule A", structural_path="Schedule A",
            clause_text="Supplier shall deliver 95% on time",
            remediation="Submit RCA", remediation_sla="48h", confidence=0.9,
        )
        output = KPIExtractionOutput(kpis=[kpi, kpi])
        stats = synth._compute_stats(output)
        assert stats["total_kpis"] == 2

    def test_redflag_stats(self):
        synth = Synthesiser()
        flag = RedFlag(
            severity="High", flag_type="Indemnification",
            section="Section 8", structural_path="Article VIII > Section 8",
            clause_text="Unlimited liability clause", explanation="No cap",
            suggested_remedy="Add liability cap", confidence=0.95,
        )
        output = RedFlagOutput(flags=[flag, flag, flag])
        stats = synth._compute_stats(output)
        assert stats["total_flags"] == 3
        assert stats["by_severity"]["High"] == 3

    def test_empty_output_empty_stats(self):
        synth = Synthesiser()
        output = BaseAnalysisOutput()
        stats = synth._compute_stats(output)
        assert stats == {}


# ── synthesise_output convenience ────────────────────────────────────

@pytest.mark.asyncio
async def test_synthesise_output_convenience():
    with patch("app.synthesis.synthesiser.call_gemini", new_callable=AsyncMock) as mock:
        mock.return_value = {"summary": "Done."}
        result = await synthesise_output(BaseAnalysisOutput(), mode="plain")
    assert result["narrative"] == "Done."
