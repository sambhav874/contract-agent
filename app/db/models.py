"""Pydantic models for MongoDB documents."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class ContractMetadata(BaseModel):
    """Metadata extracted from contract parsing."""

    contract_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    contract_type: str | None = None  # NDA / SaaS / Vendor / M&A / Employment / Other
    parties: list[dict[str, str]] = Field(default_factory=list)
    effective_date: str | None = None
    governing_law: str | None = None
    jurisdiction: str | None = None
    currency: str | None = None
    structural_map: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StructuralSection(BaseModel):
    """A section in the contract structural map."""

    section_id: str
    title: str
    level: int
    char_start: int
    char_end: int
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)


class StructuralMap(BaseModel):
    """Structural map of the contract."""

    sections: list[StructuralSection] = Field(default_factory=list)


class ChunkDocument(BaseModel):
    """A chunk document for MongoDB storage."""

    chunk_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_id: str
    chunk_level: str  # macro/meso/micro
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
    """Analysis job tracking."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_id: str
    intent: str
    sub_intents: list[str] = Field(default_factory=list)
    user_query: str | None = None
    status: str = "pending"  # pending/running/completed/failed
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    corpus_query: bool = False


# Analysis Output Schemas

class BaseAnalysisOutput(BaseModel):
    """Base class for all analysis outputs."""

    needs_more_context: bool = False
    additional_tags_needed: list[str] = Field(default_factory=list)


# Shared nested models
class KeyDate(BaseModel):
    """A key date or deadline."""
    event_name: str
    date_value: str
    description: str = ""

class MissingClause(BaseModel):
    """A missing clause that should be present."""
    clause_name: str
    description: str = ""

class UnusualClause(BaseModel):
    """An unusual or non-standard clause."""
    clause_name: str
    clause_text: str = ""
    reason: str = ""

class KeyParty(BaseModel):
    """A key party in the contract."""
    party_name: str
    role: str
    description: str = ""


# Risk Analysis
class RiskItem(BaseModel):
    """A single risk item."""

    risk_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: int = Field(ge=1, le=5)
    risk_type: str  # financial/reputational/operational/legal
    exposed_party: str
    section: str
    structural_path: str
    clause_text: str
    explanation: str
    mitigation_suggestion: str
    confidence: float = Field(ge=0.0, le=1.0)


class RiskAnalysisOutput(BaseAnalysisOutput):
    """Risk analysis output schema."""

    overall_risk_score: float = Field(ge=0.0, le=10.0)
    risk_grade: str  # A/B/C/D/F
    risks: list[RiskItem] = Field(default_factory=list)
    heatmap_by_section: dict[str, int] = Field(default_factory=dict)
    human_review_flags: list[str] = Field(default_factory=list)


# KPI Analysis
class KPIItem(BaseModel):
    """A single KPI item."""

    kpi_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    value: str
    unit: str
    kpi_type: str  # financial/timeline/volume/sla/penalty/other
    party: str
    trigger_condition: str
    section: str
    structural_path: str
    clause_text: str
    confidence: float = Field(ge=0.0, le=1.0)


class KPIExtractionOutput(BaseAnalysisOutput):
    """KPI extraction output schema."""

    kpis: list[KPIItem] = Field(default_factory=list)
    financial_summary: str = ""
    key_dates: list[KeyDate] = Field(default_factory=list)
    penalties: list[str] = Field(default_factory=list)


# Clause Analysis
class ClauseItem(BaseModel):
    """A single clause item."""

    clause_type: str
    status: str  # present/absent/modified/unusual
    section: str
    structural_path: str
    clause_text: str = ""
    deviation_notes: str = ""
    confidence: float = Field(ge=0.0, le=1.0)


class ClauseAnalysisOutput(BaseAnalysisOutput):
    """Clause analysis output schema."""

    clause_inventory: list[ClauseItem] = Field(default_factory=list)
    missing_clauses: list[MissingClause] = Field(default_factory=list)
    unusual_clauses: list[UnusualClause] = Field(default_factory=list)


# Obligation Analysis
class ObligationItem(BaseModel):
    """A single obligation item."""

    obligation_id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    party: str
    obligation_type: str  # obligation/prohibition/condition
    deadline: str = ""
    trigger_condition: str = ""
    consequence_of_breach: str = ""
    section: str
    structural_path: str
    confidence: float = Field(ge=0.0, le=1.0)


class ObligationTrackingOutput(BaseAnalysisOutput):
    """Obligation tracking output schema."""

    obligations: list[ObligationItem] = Field(default_factory=list)
    by_party: dict[str, list[ObligationItem]] = Field(default_factory=dict)
    upcoming_deadlines: list[KeyDate] = Field(default_factory=list)


# Summary Output
class SummaryOutput(BaseAnalysisOutput):
    """Summary output schema."""

    executive_summary: str
    deal_structure: str
    key_parties: list[KeyParty] = Field(default_factory=list)
    key_commercial_terms: list[str] = Field(default_factory=list)
    critical_dates: list[KeyDate] = Field(default_factory=list)
    governing_law: str = ""
    dispute_mechanism: str = ""


# Red Flag Output
class RedFlag(BaseModel):
    """A single red flag item."""

    flag_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: str  # Critical/High/Medium/Low
    flag_type: str
    section: str
    structural_path: str
    clause_text: str
    explanation: str
    suggested_remedy: str
    confidence: float = Field(ge=0.0, le=1.0)


class RedFlagOutput(BaseAnalysisOutput):
    """Red flag analysis output schema."""

    flags: list[RedFlag] = Field(default_factory=list)
    missing_clauses: list[MissingClause] = Field(default_factory=list)
    severity_summary: dict[str, int] = Field(default_factory=dict)
