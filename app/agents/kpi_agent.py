"""KPI extraction agent with confidence calibration and threshold filtering."""

from typing import Any

from app.agents.base_agent import BaseAgent
from app.db.models import KPIExtractionOutput, KPIItem

# ---------------------------------------------------------------------------
# Confidence calibration rules
#
# The LLM defaults to 1.0 for almost every item. We override this with a
# rules-based calibration that assigns realistic scores by *source section*:
#
#   1.0  — Explicit KPI table row (Article IV, labeled "KPI-N: ...")
#   0.95 — Pricing / financial table (Article III, tiered rates, discounts)
#   0.90 — Penalty accumulation / termination triggers (Article V, VII)
#   0.85 — Specification / standard (Article II weights, temperatures, counts)
#   0.82 — Reporting / audit obligation (Article VI deadlines)
#   0.80 — Definition-derived threshold (Article I numeric terms)
#
# Items that remain at < 0.80 after calibration are dropped from output.
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.80

_PATH_RULES: list[tuple[list[str], float]] = [
    # Highest confidence — explicit numbered KPI sections
    (["article iv", "section 4.0", "kpi-", "kpi-1", "kpi-2", "kpi-3", "kpi-4",
      "kpi-5", "kpi-6", "kpi-7", "kpi-8", "kpi-9", "kpi-10", "kpi-11",
      "kpi-12", "kpi-13", "kpi-14", "kpi-15"], 1.0),
    # High — Pricing / commercial tables
    (["article iii", "section 3.0", "section 3.01", "section 3.02",
      "section 3.03", "section 3.04", "volume discount", "base rate",
      "payment terms"], 0.95),
    # High — Penalty enforcement and termination triggers
    (["article v", "article vii", "section 5.", "section 7.",
      "performance improvement", "termination", "penalty cap",
      "accumulated penalties"], 0.90),
    # Medium-high — Service specification standards
    (["article ii", "section 2.", "specification", "standards",
      "minimum standard", "presentation requirement",
      "special meal requirement"], 0.85),
    # Medium — Reporting and audit obligations
    (["article vi", "section 6.", "reporting", "audit", "daily report",
      "monthly report", "quarterly"], 0.82),
    # Medium — Definitions with embedded numeric thresholds
    (["article i", "section 1.", "defined term", "definition",
      "catering window", "flight delay", "load factor", "critical flight"], 0.80),
]


def _calibrate_confidence(kpi: KPIItem) -> float:
    """Return a calibrated confidence score based on the KPI's structural path."""
    path_lower = (kpi.structural_path + " " + kpi.section).lower()
    name_lower = kpi.name.lower()

    for keywords, score in _PATH_RULES:
        if any(kw in path_lower or kw in name_lower for kw in keywords):
            return score

    # Fallback: keep whatever the model returned (may be 1.0)
    return kpi.confidence


def _apply_confidence_calibration(output: KPIExtractionOutput) -> KPIExtractionOutput:
    """
    Calibrate confidence scores and filter below the threshold.

    Returns a new KPIExtractionOutput with:
    - Realistic confidence values (not all 1.0)
    - Only KPIs with confidence >= CONFIDENCE_THRESHOLD
    """
    calibrated: list[KPIItem] = []
    for kpi in output.kpis:
        new_score = _calibrate_confidence(kpi)
        if new_score >= CONFIDENCE_THRESHOLD:
            # Rebuild with updated confidence (Pydantic model is immutable by default)
            calibrated.append(kpi.model_copy(update={"confidence": new_score}))

    return output.model_copy(update={"kpis": calibrated})


class KPIAgent(BaseAgent):
    """Agent for KPI extraction with confidence calibration."""

    output_schema = KPIExtractionOutput
    prompt_file = "prompts/kpi_agent/v1.txt"

    CONFIDENCE_THRESHOLD = CONFIDENCE_THRESHOLD

    async def analyze(
        self,
        query_plan: Any,
        contract_id: str,
        user_query: str,
    ) -> KPIExtractionOutput:
        """Extract KPIs, calibrate confidence scores, and apply threshold filter."""
        raw: KPIExtractionOutput = await self._retrieve_and_analyze(
            contract_id=contract_id,
            user_query=user_query or "Extract all KPIs, payment terms, milestones, and deadlines",
            query_plan=query_plan,
            max_rounds=query_plan.max_retrieval_rounds,
            top_k=60,
        )
        return _apply_confidence_calibration(raw)
