"""Compound query benchmark runner.

Evaluates multi-intent query decomposition, subtask routing accuracy,
and synthesis coherence.

Usage:
    python -m tests.evaluation.compound_benchmark
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from pathlib import Path
from typing import Any

from app.agents.chat_agent import ChatAgent, classify_intent, Intent
from app.agents.planner import Planner
from app.evaluation.full_evaluator import _coverage_score, _mean


COMPOUND_CASES_PATH = Path("tests/evaluation/compound_cases.json")


def load_compound_cases() -> list[dict[str, Any]]:
    data = json.loads(COMPOUND_CASES_PATH.read_text())
    return data.get("cases", [])


def _intent_match(actual: str, expected: str) -> bool:
    return actual.upper().strip() == expected.upper().strip()


def _extract_sub_intents_from_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    """Infer sub-intents from delegation events in the stream."""
    sub_intents = []
    for chunk in chunks:
        if chunk.get("type") == "delegation" and chunk.get("status") == "started":
            task = chunk.get("task", "")
            # Re-classify the task to get sub-intent
            # In production this would reuse the actual sub-intent from the flow;
            # here we approximate by running classify_intent synchronously-ish.
            # For evaluation we assume sync wrapping or pre-computed.
            pass  # async -- will handle in runner
    return sub_intents


class CompoundBenchmark:
    def __init__(self, cases: list[dict[str, Any]]) -> None:
        self.cases = cases
        self.results: list[dict[str, Any]] = []

    async def run(self) -> dict[str, Any]:
        started = time.time()
        for case in self.cases:
            print(f"[compound-eval] Running {case['id']}")
            self.results.append(await self.evaluate_case(case))

        return {
            "version": 1,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_cases": len(self.results),
            "duration_ms": int((time.time() - started) * 1000),
            "results": self.results,
            "summary": self._summarize(),
        }

    async def evaluate_case(self, case: dict[str, Any]) -> dict[str, Any]:
        contract_id = case["contract_id"]
        query = case["query"]

        result: dict[str, Any] = {
            "id": case["id"],
            "contract_id": contract_id,
            "query": query,
            "is_compound_detected": False,
            "sub_intents_detected": [],
            "routing_score": 0.0,
            "keyword_score": 0.0,
            "value_score": 0.0,
            "section_score": 0.0,
            "synthesis_score": 0.0,
            "overall_score": 0.0,
            "failures": [],
            "trace": {},
        }

        try:
            # Step 1: Intent classification on the compound query
            intent_result = await classify_intent(query, history=[])
            result["is_compound_detected"] = bool(intent_result.get("is_compound", False))
            result["trace"]["intent_classification"] = intent_result

            # Step 2: Run ChatAgent in full streaming mode
            agent = ChatAgent(contract_id)
            session_id = f"comp_eval_{case['id']}_{int(time.time())}"
            chunks: list[dict[str, Any]] = []
            answer_parts: list[str] = []

            async for chunk in agent.answer_question_stream(query, session_id=session_id):
                chunks.append(chunk)
                if chunk.get("type") == "content":
                    answer_parts.append(chunk.get("content", ""))

            answer = "".join(answer_parts)
            result["trace"]["chunks"] = chunks
            result["trace"]["answer"] = answer

            # Step 3: Evaluate sub-intent routing from delegations
            expected_sub_intents = case.get("expected_sub_intents", [])
            result["sub_intents_detected"] = self._extract_sub_intents(chunks)
            if expected_sub_intents:
                detected_set = set(result["sub_intents_detected"])
                expected_set = set(expected_sub_intents)
                matches = len(detected_set & expected_set)
                result["routing_score"] = matches / max(len(expected_set), 1)

            # Step 4: Evaluate synthesis quality
            keyword_score, _, _ = _coverage_score(case.get("expected_keywords", []), answer)
            value_score, _, _ = _coverage_score(case.get("expected_values", {}), answer)
            section_score, _, _ = _coverage_score(case.get("expected_sections", []), answer)

            result["keyword_score"] = keyword_score
            result["value_score"] = value_score
            result["section_score"] = section_score
            result["synthesis_score"] = _mean([keyword_score, value_score, section_score])

            # Step 5: Overall score
            result["overall_score"] = _mean([result["routing_score"], result["synthesis_score"]])

            # Failures
            failures: list[str] = []
            if not result["is_compound_detected"] and case.get("expected_is_compound"):
                failures.append("compound_not_detected")
            if result["routing_score"] < 1.0:
                failures.append("routing_mismatch")
            if keyword_score < 0.8:
                failures.append("incomplete_keywords")
            if value_score < 0.8:
                failures.append("missing_values")
            if section_score < 0.8:
                failures.append("missing_sections")
            result["failures"] = sorted(set(failures))

        except Exception as exc:
            result["failures"].append("runtime_error")
            result["trace"]["error"] = str(exc)
            result["trace"]["traceback"] = traceback.format_exc()

        return result

    @staticmethod
    def _extract_sub_intents(chunks: list[dict[str, Any]]) -> list[str]:
        """Extract sub-intents from delegation events."""
        sub_intents = []
        for chunk in chunks:
            if chunk.get("type") == "delegation" and chunk.get("status") == "started":
                task = chunk.get("task", "")
                # Infer intent from task description using a simple heuristic
                # In a full evaluation, classify_intent would be called here
                sub_intents.append(chunk.get("intent", "GENERAL_QUERY"))
        return sub_intents

    def _summarize(self) -> dict[str, Any]:
        scores = [r["overall_score"] for r in self.results]
        routing_scores = [r["routing_score"] for r in self.results]
        synthesis_scores = [r["synthesis_score"] for r in self.results]
        return {
            "mean_score": _mean(scores),
            "mean_routing_score": _mean(routing_scores),
            "mean_synthesis_score": _mean(synthesis_scores),
            "pass_rate": sum(1 for s in scores if s >= 0.85) / len(scores) if scores else 0.0,
            "failure_counts": self._count_failures(),
        }

    def _count_failures(self) -> dict[str, int]:
        from collections import Counter
        counts: dict[str, int] = Counter()
        for r in self.results:
            for f in r.get("failures", []):
                counts[f] += 1
        return dict(counts)


def write_report(results: dict[str, Any], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(results, indent=2, default=str))

    summary = results.get("summary", {})
    lines = [
        "# Compound Query Benchmark Report",
        "",
        f"Generated: {results.get('timestamp', '')}",
        f"Total cases: {results.get('total_cases', 0)}",
        "",
        "## Summary",
        "",
        f"- Mean overall score: {summary.get('mean_score', 0):.3f}",
        f"- Mean routing score: {summary.get('mean_routing_score', 0):.3f}",
        f"- Mean synthesis score: {summary.get('mean_synthesis_score', 0):.3f}",
        f"- Pass rate (>=0.85): {summary.get('pass_rate', 0):.1%}",
        "",
        "## Failure Counts",
    ]
    for failure, count in summary.get("failure_counts", {}).items():
        lines.append(f"- `{failure}`: {count}")

    lines.extend([
        "",
        "## Case Results",
        "",
        "| Case | Score | Routing | Synthesis | Failures |",
        "|---|---|---|---|---|",
    ])
    for case in results.get("results", []):
        failures = ", ".join(f"`{f}`" for f in case.get("failures", [])) or "None"
        lines.append(
            f"| {case.get('id')} | "
            f"{case.get('overall_score', 0):.3f} | "
            f"{case.get('routing_score', 0):.3f} | "
            f"{case.get('synthesis_score', 0):.3f} | "
            f"{failures} |"
        )

    md_path = str(Path(path).with_suffix(".md"))
    Path(md_path).write_text("\n".join(lines))
    print(f"[compound-eval] Report written: {md_path}")


async def main() -> int:
    cases = load_compound_cases()
    if not cases:
        print("No compound cases found.")
        return 0

    benchmark = CompoundBenchmark(cases)
    results = await benchmark.run()
    write_report(results, "reports/evaluation/compound_benchmark.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
