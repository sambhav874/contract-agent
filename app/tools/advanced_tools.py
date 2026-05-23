"""Advanced tools for supreme contract intelligence agent capability."""

from typing import Any
import json
from datetime import datetime
from app.tools.base import BaseTool, ToolResult
from app.db.mongodb import MongoDB
from app.retrieval.retriever import get_retriever


def _source_clause(chunk: dict[str, Any]) -> str:
    tags = chunk.get("section_type_tags") or []
    return tags[0] if tags else "General"


class CompareContractsTool(BaseTool):
    name = "compare_contracts"
    description = "Compare key metadata, clauses, parties, governing laws, and effective dates across multiple uploaded contracts in the database."
    input_schema = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id

    async def _execute(self, **kwargs) -> ToolResult:
        try:
            contracts = await MongoDB.list_contracts()
            comparison = []
            for c in contracts:
                comparison.append({
                    "contract_id": c.get("contract_id"),
                    "name": c.get("name", "Unnamed"),
                    "contract_type": c.get("contract_type", "Unknown"),
                    "effective_date": c.get("effective_date", "Unknown"),
                    "governing_law": c.get("governing_law", "Unknown"),
                    "jurisdiction": c.get("jurisdiction", "Unknown"),
                    "currency": c.get("currency", "USD"),
                    "parties": c.get("parties", []),
                })
            return ToolResult(
                success=True,
                data={
                    "contracts": comparison,
                    "summary_markdown": self._build_markdown(comparison)
                },
                metadata={"count": len(comparison)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _build_markdown(self, comparison: list) -> str:
        lines = ["| Contract Name | Parties | Effective Date | Governing Law | Jurisdiction | Currency |",
                 "|---|---|---|---|---|---|"]
        for c in comparison:
            parties_str = " vs ".join(c["parties"]) if c["parties"] else "N/A"
            lines.append(f"| {c['name']} | {parties_str} | {c['effective_date']} | {c['governing_law']} | {c['jurisdiction']} | {c['currency']} |")
        return "\n".join(lines)


class CalculatePenaltiesTool(BaseTool):
    name = "calculate_penalties"
    description = "Aggregate obligation breaches and KPI deviations, then calculate the precise accrued financial penalties and exposure in real-time."
    input_schema = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id

    async def _execute(self, **kwargs) -> ToolResult:
        try:
            breaches = await MongoDB.get_breaches(self.contract_id)
            kpis = await MongoDB.get_kpis(self.contract_id)
            kpi_map = {k.get("kpi_id"): k for k in kpis}

            total_penalty = 0.0
            detailed_calculations = []

            for b in breaches:
                kpi_id = b.get("kpi_id")
                kpi = kpi_map.get(kpi_id, {})
                penalty_info = kpi.get("penalty", "N/A")
                remediation_info = kpi.get("remediation", "N/A")

                # Check for explicit penalty amount on breach, otherwise try to calculate
                penalty_amount = b.get("penalty_amount")
                if penalty_amount is None:
                    # Parse numerical penalty description if possible or fallback
                    penalty_amount = 0.0
                    try:
                        # Simple extractor for numeric values in penalty strings e.g. "$500 per delivery delay"
                        digits = [int(s) for s in b.get("penalty_description", "").split() if s.isdigit()]
                        if digits:
                            penalty_amount = float(digits[0])
                    except:
                        pass

                total_penalty += float(penalty_amount or 0.0)
                detailed_calculations.append({
                    "breach_id": b.get("breach_id") or str(b.get("_id")),
                    "kpi_id": kpi_id,
                    "kpi_name": kpi.get("name", "Unknown KPI"),
                    "actual_value": b.get("actual_value"),
                    "target_value": b.get("target_value"),
                    "timestamp": b.get("timestamp"),
                    "severity": b.get("severity", "medium"),
                    "penalty_amount": penalty_amount,
                    "penalty_rule": penalty_info,
                    "remediation": remediation_info
                })

            contract = await MongoDB.get_contract(self.contract_id) or {}
            currency = contract.get("currency", "USD")

            return ToolResult(
                success=True,
                data={
                    "total_penalty": total_penalty,
                    "currency": currency,
                    "breaches_count": len(detailed_calculations),
                    "details": detailed_calculations,
                    "summary_markdown": f"### Accumulated Financial Exposure: **{currency} {total_penalty:,.2f}** over {len(detailed_calculations)} breach events."
                },
                metadata={"breaches_count": len(detailed_calculations)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ExtractKeyDatesTool(BaseTool):
    name = "extract_key_dates"
    description = "Scan contract clauses and extract all critical dates, including effective dates, execution dates, notices, renewal windows, milestones, and expiration dates."
    input_schema = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.retriever = get_retriever()

    async def _execute(self, **kwargs) -> ToolResult:
        try:
            # Query macro & micro chunks for date-heavy clauses
            date_chunks = await self.retriever.fetch(
                contract_id=self.contract_id,
                query="effective date termination notice duration expire expiration milestone renewal notice period",
                levels=["macro", "micro"],
                top_k=10
            )

            extracted_dates = []
            for chunk in date_chunks:
                text = chunk.get("text", "")
                # Clean up simple patterns
                if "effective date" in text.lower():
                    extracted_dates.append({
                        "type": "Effective Date",
                        "context": text[:300].strip() + "...",
                        "source_clause": _source_clause(chunk)
                    })
                if "termination" in text.lower() or "expiration" in text.lower():
                    extracted_dates.append({
                        "type": "Expiration / Termination",
                        "context": text[:300].strip() + "...",
                        "source_clause": _source_clause(chunk)
                    })
                if "notice" in text.lower() and ("days" in text.lower() or "months" in text.lower()):
                    extracted_dates.append({
                        "type": "Notice Window",
                        "context": text[:300].strip() + "...",
                        "source_clause": _source_clause(chunk)
                    })

            # Fetch core contract metadata
            contract = await MongoDB.get_contract(self.contract_id) or {}
            core_dates = [
                {"type": "Core Effective Date", "value": contract.get("effective_date", "N/A")},
                {"type": "Ingested At", "value": contract.get("created_at", "N/A")}
            ]

            return ToolResult(
                success=True,
                data={
                    "core_dates": core_dates,
                    "extracted_clauses": extracted_dates[:5]
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GenerateComplianceReportTool(BaseTool):
    name = "generate_compliance_report"
    description = "Generate a comprehensive audit-ready compliance overview of KPIs, breaches, and calculated financial exposure."
    input_schema = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, contract_id: str):
        self.contract_id = contract_id

    async def _execute(self, **kwargs) -> ToolResult:
        try:
            contract = await MongoDB.get_contract(self.contract_id) or {}
            kpis = await MongoDB.get_kpis(self.contract_id)
            breaches = await MongoDB.get_breaches(self.contract_id)

            # Simple calculations
            total_kpi = len(kpis)
            total_breach = len(breaches)
            active_breaches = len([b for b in breaches if b.get("status") == "active"])
            resolved_breaches = len([b for b in breaches if b.get("status") == "resolved"])

            total_penalty = sum(float(b.get("penalty_amount") or 0.0) for b in breaches)
            currency = contract.get("currency", "USD")

            return ToolResult(
                success=True,
                data={
                    "contract_name": contract.get("name", "Unknown"),
                    "kpis_count": total_kpi,
                    "breaches_count": total_breach,
                    "active_breaches": active_breaches,
                    "resolved_breaches": resolved_breaches,
                    "total_penalty": total_penalty,
                    "currency": currency,
                    "generated_at": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
