"""Pydantic models for MongoDB documents — corrected and extended."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ── MongoDB document models ───────────────────────────────────────────

class ContractMetadata(BaseModel):
    contract_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    contract_type: str | None = None
    parties: list[dict[str, str]] = Field(default_factory=list)
    effective_date: str | None = None
    governing_law: str | None = None
    jurisdiction: str | None = None
    currency: str | None = None
    structural_map: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StructuralSection(BaseModel):
    section_id: str
    title: str
    level: int
    char_start: int
    char_end: int
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)


class StructuralMap(BaseModel):
    sections: list[StructuralSection] = Field(default_factory=list)


class ChunkDocument(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_id: str
    chunk_level: str   # macro / meso / micro
    text: str
    token_count: int
    structural_path: str
    section_type_tags: list[str] = Field(default_factory=list)
    char_start: int
    char_end: int
    parent_chunk_id: str | None = None
    child_chunk_ids: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnalysisJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_id: str
    intent: str
    sub_intents: list[str] = Field(default_factory=list)
    user_query: str | None = None
    status: str = "pending"   # pending / running / completed / failed
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    corpus_query: bool = False


# ── Shared output sub-models ──────────────────────────────────────────

class BaseAnalysisOutput(BaseModel):
    """Base class for all analysis outputs."""
    needs_more_context: bool = False
    additional_tags_needed: list[str] = Field(default_factory=list)


class KeyDate(BaseModel):
    event_name: str
    date_value: str
    description: str = ""


class MissingClause(BaseModel):
    clause_name: str
    description: str = ""


class UnusualClause(BaseModel):
    clause_name: str
    clause_text: str = ""
    reason: str = ""


class KeyParty(BaseModel):
    party_name: str
    role: str
    description: str = ""


# ── Risk Analysis ─────────────────────────────────────────────────────

class RiskItem(BaseModel):
    risk_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: int = Field(ge=1, le=5)
    risk_type: str          # financial / reputational / operational / legal
    exposed_party: str
    section: str
    structural_path: str
    clause_text: str
    explanation: str
    mitigation_suggestion: str
    confidence: float = Field(ge=0.0, le=1.0)


class RiskAnalysisOutput(BaseAnalysisOutput):
    overall_risk_score: float = Field(ge=0.0, le=10.0)
    risk_grade: str          # A / B / C / D / F
    risks: list[RiskItem] = Field(default_factory=list)
    heatmap_by_section: dict[str, int] = Field(default_factory=dict)
    human_review_flags: list[str] = Field(default_factory=list)


# ── KPI Extraction ────────────────────────────────────────────────────

class KPIItem(BaseModel):
    kpi_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the KPI")
    name: str = Field(description="Descriptive name of the KPI (e.g., 'Late Delivery Penalty')")
    value: str = Field(description="The numeric value or threshold (e.g., '500', '99.5')")
    unit: str = Field(description="The unit of measurement (e.g., 'USD', '%', 'hours')")
    
    # ── Quantitative Fields (for SQL matching) ───────────────────────
    value_min: float | None = Field(None, description="Minimum threshold (for ranges or single values)")
    value_max: float | None = Field(None, description="Maximum threshold (only for 'between' ranges)")
    operator: str | None = Field(None, description="Operator: '>=', '<=', '==', '<', '>', or 'between'")
    consequence_value: float | None = Field(None, description="Numeric consequence (e.g., 500.0)")
    consequence_unit: str | None = Field(None, description="Unit for consequence (e.g., 'USD', '%')")
    # ────────────────────────────────────────────────────────────────

    kpi_type: str = Field(description="Category: financial / timeline / volume / sla / penalty / other")
    party: str = Field(description="The party responsible for meeting this KPI or paying the penalty")
    trigger_condition: str = Field(description="The specific condition that triggers this KPI or penalty")
    section: str = Field(description="The section title where this KPI was found")
    structural_path: str = Field(description="The full hierarchical path (e.g., 'Article IV > Section 4.1')")
    clause_text: str = Field(description="Verbatim text from the contract containing the KPI (max 60 words)")
    remediation: str | None = Field(None, description="Required corrective action if breached")
    remediation_sla: str | None = Field(None, description="Timeline for completing remediation (e.g., '24 hours', '7 days')")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0. Use 0.8-0.9 for likely but partially detailed items.")



class KPIExtractionOutput(BaseAnalysisOutput):
    kpis: list[KPIItem] = Field(description="Exhaustive list of all extracted KPIs")
    financial_summary: str = ""
    key_dates: list[KeyDate] = Field(default_factory=list)
    # NOTE: field renamed from `penalty_structure` (string) to `penalties` (list)
    # to match the prompt v3 output rules and the CLI display logic.
    penalties: list[str] = Field(default_factory=list)

    # ── backwards-compat shim ──────────────────────────────────────────
    @field_validator("penalties", mode="before")
    @classmethod
    def coerce_penalties(cls, v: Any) -> list[str]:
        """Accept either a list[str] or a plain string from older LLM outputs."""
        if isinstance(v, str):
            return [v] if v else []
        if v is None:
            return []
        return v


# ── Clause Analysis ───────────────────────────────────────────────────

class ClauseItem(BaseModel):
    clause_type: str
    status: str             # present / absent / modified / unusual
    section: str
    structural_path: str
    clause_text: str = ""
    deviation_notes: str = ""
    confidence: float = Field(ge=0.0, le=1.0)


class ClauseAnalysisOutput(BaseAnalysisOutput):
    clause_inventory: list[ClauseItem] = Field(default_factory=list)
    missing_clauses: list[MissingClause] = Field(default_factory=list)
    unusual_clauses: list[UnusualClause] = Field(default_factory=list)


# ── Obligation Tracking ───────────────────────────────────────────────

class ObligationItem(BaseModel):
    obligation_id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    party: str
    obligation_type: str    # obligation / prohibition / condition
    deadline: str = ""
    trigger_condition: str = ""
    consequence_of_breach: str = ""
    section: str
    structural_path: str
    confidence: float = Field(ge=0.0, le=1.0)


class ObligationTrackingOutput(BaseAnalysisOutput):
    obligations: list[ObligationItem] = Field(default_factory=list)
    by_party: dict[str, list[ObligationItem]] = Field(default_factory=dict)
    upcoming_deadlines: list[KeyDate] = Field(default_factory=list)


# ── Summary ───────────────────────────────────────────────────────────

class SummaryOutput(BaseAnalysisOutput):
    executive_summary: str
    deal_structure: str
    key_parties: list[KeyParty] = Field(default_factory=list)
    key_commercial_terms: list[str] = Field(default_factory=list)
    critical_dates: list[KeyDate] = Field(default_factory=list)
    governing_law: str = ""
    dispute_mechanism: str = ""


# ── Red Flag Analysis ─────────────────────────────────────────────────

class RedFlag(BaseModel):
    flag_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: str           # Critical / High / Medium / Low
    flag_type: str
    section: str
    structural_path: str
    clause_text: str
    explanation: str
    suggested_remedy: str
    confidence: float = Field(ge=0.0, le=1.0)


class RedFlagOutput(BaseAnalysisOutput):
    flags: list[RedFlag] = Field(default_factory=list)
    missing_clauses: list[MissingClause] = Field(default_factory=list)
    severity_summary: dict[str, int] = Field(default_factory=dict)
# ── Operational Event Processing ──────────────────────────────────────

# ── Operational Actuals (Performance Data) ───────────────────────────

class OperationalActual(BaseModel):
    actual_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_id: str
    kpi_id: str
    value: float
    unit: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    source: str = "manual"  # manual / email / api / erp
    metadata: dict[str, Any] = Field(default_factory=dict)

class BreachResult(BaseModel):
    breach_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_id: str
    kpi_id: str
    actual_value: float
    threshold_value: float
    operator: str
    is_breach: bool
    penalty_triggered: str | None = None
    penalty_amount: float = 0.0
    remediation: str | None = None
    remediation_sla: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

