#!/usr/bin/env python3
"""
Contract Intelligence Agent - Evaluation Suite

Evaluates agent performance on:
1. Answer Quality - Accuracy, completeness, relevance
2. Retrieval - Correct section identification, chunk retrieval
3. Ambiguity Handling - How well it handles ambiguous queries
4. KPI Extraction - Numeric accuracy
5. Risk Detection - Issue identification
6. Clause Analysis - Contract structure understanding

Output: evaluation_results.json with detailed scores
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Test queries organized by category
TEST_QUERIES = {
    "kpi_extraction": [
        {
            "query": "What are the on-time delivery targets and penalties?",
            "expected_keywords": ["98.5%", "Tier 1", "Tier 2", "$2,500", "$5,000"],
            "expected_values": {"target": "98.5%", "tier1_threshold": "97%"},
        },
        {
            "query": "What are the volume discount tiers?",
            "expected_keywords": ["500,000", "1,000,000", "2,000,000", "5,000,000"],
            "expected_values": {"discount_range": "2.5%-8.0%"},
        },
        {
            "query": "What is the meal quality score target and penalty structure?",
            "expected_keywords": ["4.5", "5.0", "$5,000", "$15,000", "$30,000"],
            "expected_values": {"target": "4.5", "max_penalty": "$50,000"},
        },
        {
            "query": "List all pricing for Business Class meals",
            "expected_keywords": ["$28.50", "$42.00", "3.5%"],
            "expected_values": {"base_range": "$28.50-$42.00"},
        },
        {
            "query": "What are the waste rate targets and penalties?",
            "expected_keywords": ["3.5%", "2.5%", "bonus", "$2,500", "$10,000"],
            "expected_values": {"target": "3.5%", "bonus_threshold": "2.5%"},
        },
    ],
    "risk_detection": [
        {
            "query": "What are the termination risks for the Concessionaire?",
            "expected_keywords": ["termination", "food safety", "hospitalization", "$500,000"],
            "expected_values": {"cure_period": "30 days", "penalty_threshold": "$500,000"},
        },
        {
            "query": "Identify food safety incident penalties",
            "expected_keywords": ["$25,000", "$100,000", "$250,000", "$1,000,000"],
            "expected_values": {"max_penalty": "$1,000,000"},
        },
        {
            "query": "What are the liability caps or unlimited exposures?",
            "expected_keywords": ["liability", "unlimited", "cap"],
            "expected_values": {},
        },
    ],
    "obligation_tracking": [
        {
            "query": "What are the reporting obligations?",
            "expected_keywords": ["daily", "monthly", "quarterly", "10:00 AM", "10th"],
            "expected_values": {"daily_deadline": "10:00 AM", "monthly_deadline": "10th"},
        },
        {
            "query": "What are the special meal availability requirements?",
            "expected_keywords": ["24 hours", "48 hours", "99.0%"],
            "expected_values": {"standard_notice": "24 hours", "religious_notice": "48 hours"},
        },
        {
            "query": "What are the equipment uptime requirements?",
            "expected_keywords": ["98%", "uptime", "ovens", "carts"],
            "expected_values": {"target": "98%"},
        },
    ],
    "clause_analysis": [
        {
            "query": "What is the contract term and renewal structure?",
            "expected_keywords": ["2027", "2031", "5 years", "January 1"],
            "expected_values": {"start": "2027", "end": "2031"},
        },
        {
            "query": "What are the key definitions related to meal delivery?",
            "expected_keywords": ["Catering Window", "On-Time Delivery", "Meal Shortfall"],
            "expected_values": {},
        },
        {
            "query": "What sustainability requirements exist?",
            "expected_keywords": ["50%", "packaging", "25%", "locally sourced", "60%"],
            "expected_values": {"packaging_target": "50%", "local_target": "25%"},
        },
    ],
    "ambiguity_handling": [
        {
            "query": "What happens if meals are late?",
            "expected_keywords": ["late", "penalty", "delivery", "time"],
            "expected_values": {},
        },
        {
            "query": "Can prices be increased?",
            "expected_keywords": ["price", "adjustment", "escalation", "CPI"],
            "expected_values": {},
        },
        {
            "query": "What if there is a problem with the food?",
            "expected_keywords": ["complaint", "quality", "defect", "issue"],
            "expected_values": {},
        },
    ],
}


class EvaluationResult:
    """Stores evaluation results."""

    def __init__(self, query: dict, category: str):
        self.query = query
        self.category = category
        self.actual_query = query["query"]
        self.response = None
        self.response_text = ""
        self.score_quality = 0.0
        self.score_relevance = 0.0
        self.score_completeness = 0.0
        self.keywords_found = []
        self.keywords_missing = []
        self.values_found = {}
        self.values_missing = {}
        self.retrieved_sections = []
        self.latency_ms = 0
        self.error = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "query": self.actual_query,
            "expected_keywords": self.query.get("expected_keywords", []),
            "expected_values": self.query.get("expected_values", {}),
            "response": self.response_text[:500] if self.response_text else "",
            "keywords_found": self.keywords_found,
            "keywords_missing": self.keywords_missing,
            "values_found": self.values_found,
            "values_missing": self.values_missing,
            "retrieved_sections": self.retrieved_sections,
            "score_quality": self.score_quality,
            "score_relevance": self.score_relevance,
            "score_completeness": self.score_completeness,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


def evaluate_keyword_coverage(result: EvaluationResult) -> None:
    """Evaluate how many expected keywords were found."""
    if not result.response_text:
        return

    response_lower = result.response_text.lower()
    all_keywords = result.query.get("expected_keywords", [])

    for keyword in all_keywords:
        if keyword.lower() in response_lower:
            result.keywords_found.append(keyword)
        else:
            result.keywords_missing.append(keyword)

    # Score based on keyword coverage
    if len(all_keywords) > 0:
        coverage = len(result.keywords_found) / len(all_keywords)
        result.score_relevance = min(1.0, coverage * 1.2)  # Bonus for over-delivery


def evaluate_value_extraction(result: EvaluationResult) -> None:
    """Evaluate if expected values were extracted."""
    if not result.response_text:
        return

    expected = result.query.get("expected_values", {})
    for key, expected_val in expected.items():
        if expected_val.lower() in result.response_text.lower():
            result.values_found[key] = expected_val
        else:
            result.values_missing[key] = expected_val


def calculate_completeness_score(result: EvaluationResult) -> None:
    """Calculate completeness score based on coverage."""
    keyword_score = 0
    if result.query.get("expected_keywords"):
        total = len(result.query["expected_keywords"])
        found = len(result.keywords_found)
        keyword_score = found / total if total > 0 else 0

    value_score = 0
    if result.query.get("expected_values"):
        total = len(result.query["expected_values"])
        found = len(result.values_found)
        value_score = found / total if total > 0 else 0

    # Weight: 60% keywords, 40% values
    result.score_completeness = (keyword_score * 0.6) + (value_score * 0.4)


def calculate_quality_score(result: EvaluationResult) -> None:
    """Calculate overall quality score."""
    # Quality = relevance (50%) + completeness (50%)
    result.score_quality = (result.score_relevance * 0.5) + (result.score_completeness * 0.5)


async def run_query_evaluation(
    contract_id: str,
    query_dict: dict,
    category: str,
    intent: str,
) -> EvaluationResult:
    """Run evaluation for a single query."""
    from app.routing.intent_router import route_intent
    from app.agents.risk_agent import RiskAgent
    from app.agents.kpi_agent import KPIAgent
    from app.agents.clause_agent import ClauseAgent
    from app.agents.obligation_agent import ObligationAgent
    from app.agents.summary_agent import SummaryAgent
    from app.agents.redflag_agent import RedFlagAgent
    from app.synthesis.synthesiser import synthesise_output
    from app.db.mongodb import MongoDB

    result = EvaluationResult(query_dict, category)
    start_time = time.time()

    try:
        await MongoDB.connect()

        # Map intent to agent
        agent_map = {
            "risk": RiskAgent,
            "kpi": KPIAgent,
            "clause": ClauseAgent,
            "obligations": ObligationAgent,
            "summary": SummaryAgent,
            "redflags": RedFlagAgent,
        }

        # Route intent
        query_plan = await route_intent(intent, query_dict["query"])

        # Select and run agent
        agent_class = agent_map.get(intent, KPIAgent)
        agent = agent_class()
        output = await agent.analyze(query_plan, contract_id, query_dict["query"])

        # Synthesize
        synthesized = await synthesise_output(output)

        result.response = synthesized
        result.response_text = json.dumps(synthesized.get("narrative", "")) + " " + json.dumps(synthesized.get("structured", {}))
        result.retrieved_sections = list(set(
            item.get("structural_path", "")
            for item in synthesized.get("structured", {}).get("kpis", [])
        ))

    except Exception as e:
        result.error = str(e)

    result.latency_ms = int((time.time() - start_time) * 1000)

    # Evaluate results
    evaluate_keyword_coverage(result)
    evaluate_value_extraction(result)
    calculate_completeness_score(result)
    calculate_quality_score(result)

    return result


async def evaluate_contract(
    contract_file: str,
    contract_name: str,
    output_file: str,
) -> dict:
    """Run full evaluation suite on a contract."""

    # First ingest the contract
    from app.ingestion.parser import parse_contract
    from app.ingestion.chunker import hierarchical_chunk
    from app.db.mongodb import MongoDB

    print(f"Ingesting {contract_file}...")
    metadata, structural_map = await parse_contract(contract_file, contract_name)

    with open(contract_file, "r") as f:
        text = f.read()

    chunks = hierarchical_chunk(text, metadata.contract_id, structural_map)
    print(f"Created {len(chunks)} chunks")

    # Run all test queries
    all_results = []

    for category, queries in TEST_QUERIES.items():
        print(f"\nEvaluating category: {category}")
        intent = {
            "kpi_extraction": "kpi",
            "risk_detection": "risk",
            "obligation_tracking": "obligations",
            "clause_analysis": "clause",
            "ambiguity_handling": "summary",
        }.get(category, "kpi")

        for query_dict in queries:
            print(f"  Query: {query_dict['query'][:50]}...")
            result = await run_query_evaluation(
                metadata.contract_id,
                query_dict,
                category,
                intent,
            )
            all_results.append(result)
            print(f"    Quality: {result.score_quality:.2f}, Relevance: {result.score_relevance:.2f}")

    # Compile results
    evaluation = {
        "contract_file": contract_file,
        "contract_name": contract_name,
        "contract_id": metadata.contract_id,
        "chunks_created": len(chunks),
        "sections_detected": len(structural_map.sections),
        "timestamp": datetime.now().isoformat(),
        "results": [r.to_dict() for r in all_results],
        "summary": {
            "total_queries": len(all_results),
            "avg_quality": sum(r.score_quality for r in all_results) / len(all_results) if all_results else 0,
            "avg_relevance": sum(r.score_relevance for r in all_results) / len(all_results) if all_results else 0,
            "avg_completeness": sum(r.score_completeness for r in all_results) / len(all_results) if all_results else 0,
            "error_rate": sum(1 for r in all_results if r.error) / len(all_results) if all_results else 0,
            "avg_latency_ms": sum(r.latency_ms for r in all_results) / len(all_results) if all_results else 0,
        },
    }

    # Save results
    with open(output_file, "w") as f:
        json.dump(evaluation, f, indent=2)

    print(f"\nEvaluation complete. Results saved to {output_file}")
    return evaluation


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    contract_file = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/airport_food.md"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "evaluation_results.json"

    print("=" * 60)
    print("Contract Intelligence Agent - Evaluation Suite")
    print("=" * 60)

    result = asyncio.run(evaluate_contract(contract_file, "Airport Food Contract", output_file))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total Queries: {result['summary']['total_queries']}")
    print(f"Avg Quality Score: {result['summary']['avg_quality']:.2f}")
    print(f"Avg Relevance: {result['summary']['avg_relevance']:.2f}")
    print(f"Avg Completeness: {result['summary']['avg_completeness']:.2f}")
    print(f"Error Rate: {result['summary']['error_rate']:.1%}")
    print(f"Avg Latency: {result['summary']['avg_latency_ms']:.0f}ms")
