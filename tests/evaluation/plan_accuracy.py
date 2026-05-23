"""QueryPlan ground-truth scorer.

Evaluates how well route_intent() produces correct chunk levels,
section tags, retrieval rounds, and map_pass settings.

Usage:
    python -m pytest tests/evaluation/plan_accuracy.py -v
    python -m tests.evaluation.plan_accuracy --cases data/plan_ground_truth.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from app.routing.intent_router import route_intent, QueryPlan


@dataclass
class PlanExpectation:
    intent: str
    expected_levels: list[str]
    expected_tags: list[str]
    expected_map_pass: bool
    expected_rounds: int
    expected_schema: str = ""
    expected_mode: str = "plain"


@dataclass
class PlanScoreResult:
    levels_correct: bool
    map_pass_correct: bool
    rounds_correct: bool
    tags_precision: float
    tags_recall: float
    schema_correct: bool
    mode_correct: bool

    @property
    def overall(self) -> float:
        return (
            (1.0 if self.levels_correct else 0.0) * 0.25
            + (1.0 if self.map_pass_correct else 0.0) * 0.15
            + (1.0 if self.rounds_correct else 0.0) * 0.15
            + self.tags_precision * 0.20
            + self.tags_recall * 0.10
            + (1.0 if self.schema_correct else 0.0) * 0.10
            + (1.0 if self.mode_correct else 0.0) * 0.05
        )


def _set_eq(a: list[str], b: list[str]) -> bool:
    return set(x.lower() for x in a) == set(x.lower() for x in b)


def _tag_precision_recall(actual: list[str], expected: list[str]) -> tuple[float, float]:
    if not expected:
        return 1.0, 1.0
    actual_set = set(a.lower() for a in actual)
    expected_set = set(e.lower() for e in expected)
    intersection = actual_set & expected_set
    precision = len(intersection) / len(actual_set) if actual_set else 0.0
    recall = len(intersection) / len(expected_set) if expected_set else 0.0
    return precision, recall


class PlanAccuracyScorer:
    def __init__(self, expectations: list[PlanExpectation]) -> None:
        self.expectations = expectations
        self.results: list[tuple[PlanExpectation, PlanScoreResult, QueryPlan]] = []

    async def run(self) -> dict[str, Any]:
        for exp in self.expectations:
            plan = await route_intent(exp.intent, user_query=f"test query for {exp.intent}")
            result = self._score(exp, plan)
            self.results.append((exp, result, plan))

        return {
            "total": len(self.results),
            "mean_score": sum(r.overall for _, r, _ in self.results) / len(self.results) if self.results else 0.0,
            "per_intent": self._per_intent_summary(),
            "details": self._details(),
        }

    def _score(self, exp: PlanExpectation, plan: QueryPlan) -> PlanScoreResult:
        levels_c = _set_eq(plan.chunk_levels, exp.expected_levels)
        map_c = plan.map_pass_required == exp.expected_map_pass
        rounds_c = plan.max_retrieval_rounds == exp.expected_rounds
        prec, rec = _tag_precision_recall(plan.priority_section_tags, exp.expected_tags)
        schema_c = (not exp.expected_schema) or (plan.output_schema_name.lower() == exp.expected_schema.lower())
        mode_c = plan.analysis_mode.lower() == exp.expected_mode.lower()
        return PlanScoreResult(
            levels_correct=levels_c,
            map_pass_correct=map_c,
            rounds_correct=rounds_c,
            tags_precision=prec,
            tags_recall=rec,
            schema_correct=schema_c,
            mode_correct=mode_c,
        )

    def _per_intent_summary(self) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[float]] = defaultdict(list)
        for exp, result, _ in self.results:
            groups[exp.intent].append(result.overall)
        return {
            intent: {"count": len(scores), "mean_score": sum(scores) / len(scores)}
            for intent, scores in sorted(groups.items())
        }

    def _details(self) -> list[dict[str, Any]]:
        out = []
        for exp, result, plan in self.results:
            out.append({
                "intent": exp.intent,
                "expected": {
                    "levels": exp.expected_levels,
                    "tags": exp.expected_tags,
                    "map_pass": exp.expected_map_pass,
                    "rounds": exp.expected_rounds,
                },
                "actual": {
                    "levels": plan.chunk_levels,
                    "tags": plan.priority_section_tags,
                    "map_pass": plan.map_pass_required,
                    "rounds": plan.max_retrieval_rounds,
                },
                "score": result.overall,
                "breakdown": {
                    "levels": result.levels_correct,
                    "map_pass": result.map_pass_correct,
                    "rounds": result.rounds_correct,
                    "tags_precision": result.tags_precision,
                    "tags_recall": result.tags_recall,
                },
            })
        return out


# Default expectations based on static fallback table
DEFAULT_EXPECTATIONS = [
    PlanExpectation("CLAUSE_LOOKUP", ["meso"], [], True, 3, "ClauseAnalysisOutput", "legal"),
    PlanExpectation("SUMMARY", ["macro"], [], True, 2, "SummaryOutput", "plain"),
    PlanExpectation("OBLIGATION_TRACK", ["meso", "micro"], [], False, 3, "ObligationTrackingOutput", "plain"),
    PlanExpectation("KPI_QUERY", ["micro", "meso"], [], True, 4, "KPIExtractionOutput", "plain"),
    PlanExpectation("COMPLIANCE", ["meso", "micro"], [], False, 3, "KPIExtractionOutput", "plain"),
    PlanExpectation("RISK_ANALYSIS", ["macro", "meso"], [], True, 3, "RiskAnalysisOutput", "legal"),
    PlanExpectation("DATA_VIZ", ["micro", "meso"], [], False, 3, "KPIExtractionOutput", "plain"),
    PlanExpectation("DIAGRAM", ["macro", "meso"], [], True, 2, "", "plain"),
    PlanExpectation("QA_GENERATE", ["macro"], [], True, 2, "", "plain"),
    PlanExpectation("QA_ANSWER", ["meso", "micro"], [], False, 4, "", "plain"),
    PlanExpectation("CONVERSATIONAL", [], [], False, 0, "", "plain"),
    PlanExpectation("GENERAL_QUERY", ["meso"], [], False, 3, "", "plain"),
]


# ── pytest integration ────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestPlanAccuracy:
    @pytest.fixture
    async def scorer(self):
        s = PlanAccuracyScorer(DEFAULT_EXPECTATIONS)
        return s

    async def test_all_intents_scored(self, scorer):
        results = await scorer.run()
        assert results["total"] == len(DEFAULT_EXPECTATIONS)
        assert results["mean_score"] >= 0.0

    async def test_conversational_has_empty_levels(self, scorer):
        await scorer.run()
        for exp, result, plan in scorer.results:
            if exp.intent == "CONVERSATIONAL":
                assert plan.chunk_levels == []
                assert plan.max_retrieval_rounds == 0

    async def test_kpi_has_at_least_3_rounds(self, scorer):
        await scorer.run()
        for exp, result, plan in scorer.results:
            if exp.intent in ("KPI_QUERY", "COMPLIANCE"):
                assert plan.max_retrieval_rounds >= 3


# ── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QueryPlan ground-truth scorer")
    parser.add_argument("--cases", default="", help="Path to JSON expectations file")
    parser.add_argument("--output", default="reports/evaluation/plan_accuracy.json", help="Output JSON path")
    return parser


async def main() -> int:
    args = build_parser().parse_args()
    if args.cases:
        raw = json.loads(Path(args.cases).read_text())
        expectations = [PlanExpectation(**item) for item in raw]
    else:
        expectations = DEFAULT_EXPECTATIONS

    scorer = PlanAccuracyScorer(expectations)
    results = await scorer.run()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(results, indent=2, default=str))
    print(f"[plan-eval] Mean score: {results['mean_score']:.3f}")
    print(f"[plan-eval] Per-intent breakdown:")
    for intent, stats in results["per_intent"].items():
        print(f"  {intent}: {stats['mean_score']:.3f} ({stats['count']} cases)")
    print(f"[plan-eval] Report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
