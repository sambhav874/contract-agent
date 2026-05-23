"""Generate golden evaluation cases from contract fixtures.

This script parsers contract markdowns and produces a golden_cases.json file
with ~100 cases covering all intents.

Usage:
    python scripts/generate_golden_cases.py
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


CONTRACT_DIR = Path("tests/fixtures/contracts")
OUTPUT = Path("tests/evaluation/cases/golden_cases.json")


@dataclass
class GoldenCase:
    id: str
    category: str
    contract_id: str
    contract_file: str
    contract_name: str
    query: str
    expected_intent: str
    expected_agent: str | None = None
    expected_sections: list[str] | None = None
    expected_keywords: list[str] | None = None
    expected_values: dict[str, str] | None = None
    expected_tools: list[str] | None = None
    tool_checks: list[dict[str, Any]] | None = None
    ragas_ground_truth: str = ""


class ContractParser:
    """Parse a contract markdown into structured sections."""

    def __init__(self, text: str, base_name: str) -> None:
        self.text = text
        self.base_name = base_name
        self.sections: list[dict[str, Any]] = []
        self.penalties: list[dict[str, Any]] = []
        self.obligations: list[dict[str, Any]] = []
        self.dates: list[dict[str, Any]] = []
        self._parse()

    def _parse(self) -> None:
        # Sections like "## ARTICLE 4: PERFORMANCE STANDARDS"
        article_pattern = re.compile(r"^##?\s*(ARTICLE\s+[^:]+):\s*(.+)$", re.IGNORECASE | re.MULTILINE)
        section_pattern = re.compile(r"^###?\s*(Section?\s+[^:]+):\s*(.+)$", re.IGNORECASE | re.MULTILINE)

        for m in article_pattern.finditer(self.text):
            self.sections.append({
                "type": "article",
                "id": m.group(1).strip(),
                "title": m.group(2).strip(),
                "start": m.start(),
            })

        for m in section_pattern.finditer(self.text):
            self.sections.append({
                "type": "section",
                "id": m.group(1).strip(),
                "title": m.group(2).strip(),
                "start": m.start(),
            })

        # Sort by position
        self.sections.sort(key=lambda s: s.get("start", 0))

        # Extract penalties: formats like "**50,000 INR** penalty" or "$5000 penalty"
        self.penalties = self._extract_penalties()
        # Extract obligations: "shall", "must", "obligated"
        self.obligations = self._extract_obligations()
        # Extract dates: date-like patterns
        self.dates = self._extract_dates()

    def _extract_penalties(self) -> list[dict[str, Any]]:
        penalties = []
        penalty_re = re.compile(r"([\d,]+(?:\.\d+)?)\s*(INR|USD|\$)\s*(penalty|credit|charge|fine)", re.IGNORECASE)
        for m in penalty_re.finditer(self.text):
            penalties.append({
                "amount": m.group(1),
                "currency": m.group(2),
                "type": m.group(3),
                "context": self.text[max(0, m.start() - 200):m.end() + 200],
            })
        return penalties

    def _extract_obligations(self) -> list[dict[str, Any]]:
        obligations = []
        obligation_re = re.compile(r"^(.*\b(?:shall|must|obligated|required)\b.*)$", re.IGNORECASE | re.MULTILINE)
        m = obligation_re.search(self.text)
        if m:
            # Limit to first 10 sentences for brevity
            context = self.text[max(0, m.start() - 300):m.end() + 300]
            obligations.append({
                "text": m.group(1).strip(),
                "context": context,
            })
        return obligations

    def _extract_dates(self) -> list[dict[str, Any]]:
        dates = []
        date_re = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})")
        for m in date_re.finditer(self.text):
            dates.append({
                "date": m.group(0),
                "context": self.text[max(0, m.start() - 50):m.end() + 50],
            })
        return dates


def generate_cases_from_contract(path: Path) -> list[GoldenCase]:
    text = path.read_text()
    base_name = path.stem
    parser = ContractParser(text, base_name)
    cases: list[GoldenCase] = []

    # 1. Summary case
    cases.append(GoldenCase(
        id=f"{base_name}_summary",
        category="summary",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="Summarize this contract.",
        expected_intent="SUMMARY",
        expected_agent="SummaryAgent",
        expected_sections=[s["id"] for s in parser.sections[:3]],
        expected_keywords=["effective date", "parties",],
        ragas_ground_truth=f"High-level summary of {base_name}."[:200],
    ))

    # 2. Clause lookup per major section
    for section in parser.sections[:5]:
        sid = section["id"].replace(" ", "_")
        cases.append(GoldenCase(
            id=f"{base_name}_clause_{sid}",
            category="clause_analysis",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query=f"Explain {section['id']}",
            expected_intent="CLAUSE_LOOKUP",
            expected_agent="ClauseAgent",
            expected_sections=[section["id"]],
            expected_keywords=[section["title"]]
        ))

    # 3. KPI query if penalties found
    if parser.penalties:
        penalty = parser.penalties[0]
        cases.append(GoldenCase(
            id=f"{base_name}_kpi_penalty",
            category="kpi_extraction",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query="What are the penalties and KPIs?",
            expected_intent="KPI_QUERY",
            expected_agent="KPIAgent",
            expected_keywords=[penalty["amount"], penalty["currency"], "penalty"],
            expected_values={"penalty": penalty["amount"] + " " + penalty["currency"]},
        ))

    # 4. Obligation tracking
    if parser.obligations:
        obligation = parser.obligations[0]
        cases.append(GoldenCase(
            id=f"{base_name}_obligation_1",
            category="obligation_tracking",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query="What are the obligations in this contract?",
            expected_intent="OBLIGATION_TRACK",
            expected_agent="ObligationAgent",
            expected_keywords=["shall", "must"],
            ragas_ground_truth=obligation["context"][:200],
        ))

    # 5. Risk analysis
    cases.append(GoldenCase(
        id=f"{base_name}_risk_1",
        category="risk_detection",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="What are the main risks?",
        expected_intent="RISK_ANALYSIS",
        expected_agent="RiskAgent",
        expected_keywords=["termination", "liability", "damages"],
    ))

    # 6. General query about parties
    cases.append(GoldenCase(
        id=f"{base_name}_parties",
        category="general_query",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="Who are the parties?",
        expected_intent="GENERAL_QUERY",
        expected_keywords=["party", "parties"],
    ))

    # 7. Key dates
    if parser.dates:
        first_date = parser.dates[0]
        cases.append(GoldenCase(
            id=f"{base_name}_key_dates",
            category="key_dates",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query="What are the key dates?",
            expected_intent="GENERAL_QUERY",
            expected_keywords=["date", "effective", "term"],
            expected_values={"effective_date": first_date["date"]},
        ))

    # 8. Compliance
    cases.append(GoldenCase(
        id=f"{base_name}_compliance_1",
        category="compliance",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="Generate a compliance report.",
        expected_intent="COMPLIANCE",
        expected_tools=["generate_compliance_report"],
        expected_keywords=["breach", "penalty", "KPI"],
    ))

    # 9. QA generation
    cases.append(GoldenCase(
        id=f"{base_name}_qa_generate",
        category="qa_generation",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="What questions should I ask about this contract?",
        expected_intent="QA_GENERATE",
        expected_keywords=["question"],
    ))

    # 10. Conversational
    cases.append(GoldenCase(
        id=f"{base_name}_conversational",
        category="conversational",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="Hello, what can you do?",
        expected_intent="CONVERSATIONAL",
        expected_keywords=["help", "can do"],
    ))

    # 11. Add targeted KPI cases per penalty
    for i, penalty in enumerate(parser.penalties[:3]):
        cases.append(GoldenCase(
            id=f"{base_name}_kpi_specific_{i}",
            category="kpi_extraction",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query=f"What is the penalty for {penalty.get('type', 'violation')}?",
            expected_intent="KPI_QUERY",
            expected_agent="KPIAgent",
            expected_keywords=[penalty["amount"], penalty["currency"], "penalty"],
            expected_values={"penalty": penalty["amount"] + " " + penalty["currency"]},
        ))

    # 12. Add targeted clause questions per section
    for i, section in enumerate(parser.sections[:5]):
        sid = section["id"].replace(" ", "_")
        cases.append(GoldenCase(
            id=f"{base_name}_clause_q_{sid}",
            category="clause_analysis",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query=f"What does {section['id']} say about {section['title']}?",
            expected_intent="CLAUSE_LOOKUP",
            expected_agent="ClauseAgent",
            expected_sections=[section["id"]],
            expected_keywords=[section["title"]],
        ))

    # 13. Add targeted obligation cases
    for i, obligation in enumerate(parser.obligations[:2]):
        cases.append(GoldenCase(
            id=f"{base_name}_obligation_specific_{i}",
            category="obligation_tracking",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query="What obligations does the supplier have?",
            expected_intent="OBLIGATION_TRACK",
            expected_agent="ObligationAgent",
            expected_keywords=["shall", "must", "obligated"],
            ragas_ground_truth=obligation["context"][:150],
        ))

    # 14. Add risk cases per section
    for i, section in enumerate(parser.sections[:3]):
        sid = section["id"].replace(" ", "_")
        cases.append(GoldenCase(
            id=f"{base_name}_risk_{sid}",
            category="risk_detection",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query=f"What are the risks in {section['id']}?",
            expected_intent="RISK_ANALYSIS",
            expected_agent="RiskAgent",
            expected_sections=[section["id"]],
            expected_keywords=["risk", "liability", "termination", "damages"],
        ))

    # 15. Add general factual queries
    cases.append(GoldenCase(
        id=f"{base_name}_general_governing_law",
        category="general_query",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="What is the governing law?",
        expected_intent="GENERAL_QUERY",
        expected_keywords=["governing law", "jurisdiction"],
    ))

    cases.append(GoldenCase(
        id=f"{base_name}_general_termination",
        category="general_query",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="How can this contract be terminated?",
        expected_intent="GENERAL_QUERY",
        expected_keywords=["termination", "terminate", "notice"],
    ))

    # 16. Add conversational variants
    cases.append(GoldenCase(
        id=f"{base_name}_conv_thanks",
        category="conversational",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="Thank you for your help.",
        expected_intent="CONVERSATIONAL",
        expected_keywords=["welcome"],
    ))

    cases.append(GoldenCase(
        id=f"{base_name}_conv_capabilities",
        category="conversational",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="What can you help me with?",
        expected_intent="CONVERSATIONAL",
        expected_keywords=["help", "capabilities"],
    ))

    # 17. Add red flag / QA variants
    cases.append(GoldenCase(
        id=f"{base_name}_redflags",
        category="redflags",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="What red flags should I watch for?",
        expected_intent="RISK_ANALYSIS",
        expected_agent="RiskAgent",
        expected_keywords=["red flag", "risk", "warning"],
    ))

    cases.append(GoldenCase(
        id=f"{base_name}_qa_answer",
        category="qa_answer",
        contract_id=base_name,
        contract_file=str(path),
        contract_name=base_name.replace("_", " ").title(),
        query="What is the penalty for late delivery?",
        expected_intent="QA_ANSWER",
        expected_keywords=["penalty", "late", "delivery"],
    ))

    # 18. Add multi-section compound cases
    if len(parser.sections) >= 2:
        s1 = parser.sections[0]
        s2 = parser.sections[1]
        cases.append(GoldenCase(
            id=f"{base_name}_compound_1",
            category="compound_orchestration",
            contract_id=base_name,
            contract_file=str(path),
            contract_name=base_name.replace("_", " ").title(),
            query=f"Explain {s1['id']} and {s2['id']}",
            expected_intent="CLAUSE_LOOKUP",
            expected_sections=[s1["id"], s2["id"]],
            expected_keywords=[s1["title"], s2["title"]],
        ))

    return cases


def main() -> int:
    all_cases: list[GoldenCase] = []
    for path in CONTRACT_DIR.glob("*.md"):
        try:
            all_cases.extend(generate_cases_from_contract(path))
        except Exception as exc:
            print(f"[gen] Error processing {path}: {exc}")

    # Serialize
    data = {
        "version": 1,
        "description": f"Golden cases for full backend evaluation of contract-agent. Auto-generated {len(all_cases)} cases from contract fixtures.",
        "cases": [],
    }

    for i, case in enumerate(all_cases):
        case.id = f"case_{i:04d}_{case.id}"  # Ensure unique IDs
        case_dict = asdict(case)
        # Clean up None values
        case_dict = {k: v for k, v in case_dict.items() if v is not None}
        data["cases"].append(case_dict)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2, default=str))
    print(f"[gen] Generated {len(data['cases'])} golden cases -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
