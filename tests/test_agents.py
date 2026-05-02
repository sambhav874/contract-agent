"""Tests for analysis agents."""

import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_intent_routing_risk():
    """Test intent routing for risk analysis."""
    from app.routing.intent_router import route_intent

    plan = await route_intent("risk", None, None)

    assert plan.intent == "risk" or plan.priority_section_tags
    assert "meso" in plan.chunk_levels or "macro" in plan.chunk_levels


@pytest.mark.asyncio
async def test_intent_routing_kpi():
    """Test intent routing for KPI extraction."""
    from app.routing.intent_router import route_intent

    plan = await route_intent("kpi", None, None)

    assert plan.intent == "kpi" or plan.priority_section_tags
    # KPI should focus on payment, milestone, sla tags
    assert "micro" in plan.chunk_levels or "meso" in plan.chunk_levels


@pytest.mark.asyncio
async def test_intent_routing_summary():
    """Test intent routing for summary."""
    from app.routing.intent_router import route_intent

    plan = await route_intent("summary", None, None)

    assert plan.intent == "summary"
    assert "macro" in plan.chunk_levels  # Summary uses macro chunks


def test_agent_models_valid():
    """Test that agent output models are valid."""
    from app.db.models import (
        RiskAnalysisOutput, KPIExtractionOutput, ClauseAnalysisOutput,
        ObligationTrackingOutput, SummaryOutput, RedFlagOutput
    )

    # Test RiskAnalysisOutput
    risk_output = RiskAnalysisOutput(
        overall_risk_score=5.0,
        risk_grade="C",
        risks=[],
        heatmap_by_section={},
        human_review_flags=[]
    )
    assert risk_output.overall_risk_score == 5.0
    assert risk_output.risk_grade == "C"

    # Test KPIExtractionOutput
    kpi_output = KPIExtractionOutput(
        kpis=[],
        financial_summary="",
        key_dates=[],
        penalty_structure=""
    )
    assert kpi_output.kpis is not None

    # Test ClauseAnalysisOutput
    clause_output = ClauseAnalysisOutput(
        clause_inventory=[],
        missing_clauses=[],
        unusual_clauses=[]
    )
    assert clause_output.clause_inventory is not None

    # Test ObligationTrackingOutput
    obligation_output = ObligationTrackingOutput(
        obligations=[],
        by_party={},
        upcoming_deadlines=[]
    )
    assert obligation_output.obligations is not None

    # Test SummaryOutput
    summary_output = SummaryOutput(
        executive_summary="",
        deal_structure="",
        key_parties=[],
        key_commercial_terms=[],
        critical_dates=[],
        governing_law="",
        dispute_mechanism=""
    )
    assert summary_output.executive_summary is not None

    # Test RedFlagOutput
    redflag_output = RedFlagOutput(
        flags=[],
        missing_clauses=[],
        severity_summary={}
    )
    assert redflag_output.flags is not None


def test_risk_item_structure():
    """Test RiskItem model structure."""
    from app.db.models import RiskItem

    risk = RiskItem(
        severity=4,
        risk_type="financial",
        exposed_party="Client",
        section="Liability Cap",
        structural_path="Article 9 > Section 9.2",
        clause_text="Liability shall not exceed fees paid",
        explanation="Cap may be insufficient for large claims",
        mitigation_suggestion="Negotiate higher cap or remove cap for gross negligence",
        confidence=0.85
    )

    assert risk.severity == 4
    assert risk.risk_type == "financial"
    assert 0.0 <= risk.confidence <= 1.0


def test_kpi_item_structure():
    """Test KPIItem model structure."""
    from app.db.models import KPIItem

    kpi = KPIItem(
        name="Subscription Fee",
        value="$120,000",
        unit="USD",
        kpi_type="financial",
        party="Customer",
        trigger_condition="Annual",
        section="Fees and Payment",
        structural_path="Article 4",
        clause_text="Customer shall pay $120,000 per year",
        confidence=0.95
    )

    assert kpi.name == "Subscription Fee"
    assert kpi.value == "$120,000"
    assert kpi.kpi_type == "financial"


def test_clause_item_structure():
    """Test ClauseItem model structure."""
    from app.db.models import ClauseItem

    clause = ClauseItem(
        clause_type="limitation_of_liability",
        status="present",
        section="Article 9",
        structural_path="Article 9",
        clause_text="Liability cap applies",
        deviation_notes="Standard cap",
        confidence=0.9
    )

    assert clause.clause_type == "limitation_of_liability"
    assert clause.status in ["present", "absent", "modified", "unusual"]


def test_obligation_item_structure():
    """Test ObligationItem model structure."""
    from app.db.models import ObligationItem

    obligation = ObligationItem(
        text="Customer shall pay within 45 days",
        party="Customer",
        obligation_type="obligation",
        deadline="45 days from invoice",
        trigger_condition="Invoice receipt",
        consequence_of_breach="Late fees",
        section="Payment Terms",
        structural_path="Article 3",
        confidence=0.92
    )

    assert obligation.obligation_type in ["obligation", "prohibition", "condition"]


def test_redflag_structure():
    """Test RedFlag model structure."""
    from app.db.models import RedFlag

    flag = RedFlag(
        severity="High",
        flag_type="liability_cap",
        section="Limitation of Liability",
        structural_path="Article 7",
        clause_text="Liability capped at fees paid",
        explanation="Cap may be too low",
        suggested_remedy="Increase cap or carve out certain damages",
        confidence=0.8
    )

    assert flag.severity in ["Critical", "High", "Medium", "Low"]


def test_base_agent_structure():
    """Test that BaseAgent has required methods."""
    from app.agents.base_agent import BaseAgent

    assert hasattr(BaseAgent, "analyse")
    assert hasattr(BaseAgent, "load_prompt")
    assert hasattr(BaseAgent, "self_correct")


def test_agents_inherit_base():
    """Test that all agents inherit from BaseAgent."""
    from app.agents.base_agent import BaseAgent
    from app.agents.risk_agent import RiskAgent
    from app.agents.kpi_agent import KPIAgent
    from app.agents.clause_agent import ClauseAgent
    from app.agents.obligation_agent import ObligationAgent
    from app.agents.summary_agent import SummaryAgent
    from app.agents.redflag_agent import RedFlagAgent

    # Check inheritance
    assert issubclass(RiskAgent, BaseAgent)
    assert issubclass(KPIAgent, BaseAgent)
    assert issubclass(ClauseAgent, BaseAgent)
    assert issubclass(ObligationAgent, BaseAgent)
    assert issubclass(SummaryAgent, BaseAgent)
    assert issubclass(RedFlagAgent, BaseAgent)

    # Check required attributes
    for agent_class in [RiskAgent, KPIAgent, ClauseAgent, ObligationAgent, SummaryAgent, RedFlagAgent]:
        assert hasattr(agent_class, "output_schema")
        assert hasattr(agent_class, "prompt_file")
        assert hasattr(agent_class, "analyse")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
