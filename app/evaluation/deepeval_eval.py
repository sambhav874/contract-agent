"""DeepEval benchmark adapter for contract-agent.

This scores actual agent answers and actual retrieved context with DeepEval's
RAG metrics, using Gemini as the judge so evaluation does not depend on OpenAI.
"""

from __future__ import annotations

import os
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import settings

# Keep DeepEval local/offline unless a caller explicitly opts in elsewhere.
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")


DEFAULT_DEEPEVAL_THRESHOLDS = {
    "answer_relevancy": 0.90,
    "faithfulness": 0.92,
    "contextual_precision": 0.90,
    "contextual_recall": 0.90,
    "contextual_relevancy": 0.90,
    "aggregate": 0.90,
}


@dataclass
class DeepEvalSample:
    """One already-executed RAG/agent interaction to benchmark."""

    question: str
    answer: str
    contexts: list[str]
    expected_output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class DeepEvalEvaluator:
    """Run DeepEval RAG metrics over captured agent traces."""

    def __init__(
        self,
        judge_model: str | None = None,
        thresholds: dict[str, float] | None = None,
        include_reason: bool = True,
    ):
        self.judge_model = judge_model or settings.gemini_fast_model
        self.thresholds = thresholds or DEFAULT_DEEPEVAL_THRESHOLDS
        self.include_reason = include_reason
        self._judge = None

    def _get_judge(self):
        if self._judge is None:
            from deepeval.models import GeminiModel

            self._judge = GeminiModel(
                model=self.judge_model,
                api_key=settings.gemini_api_key,
                temperature=0,
            )
        return self._judge

    def _metric_specs(self, sample: DeepEvalSample) -> list[tuple[str, Any]]:
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            ContextualRelevancyMetric,
            FaithfulnessMetric,
        )

        judge = self._get_judge()
        specs: list[tuple[str, Any]] = [
            (
                "answer_relevancy",
                AnswerRelevancyMetric(
                    threshold=self.thresholds["answer_relevancy"],
                    model=judge,
                    include_reason=self.include_reason,
                    async_mode=False,
                ),
            ),
            (
                "faithfulness",
                FaithfulnessMetric(
                    threshold=self.thresholds["faithfulness"],
                    model=judge,
                    include_reason=self.include_reason,
                    async_mode=False,
                ),
            ),
            (
                "contextual_relevancy",
                ContextualRelevancyMetric(
                    threshold=self.thresholds["contextual_relevancy"],
                    model=judge,
                    include_reason=self.include_reason,
                    async_mode=False,
                ),
            ),
        ]

        if sample.expected_output:
            specs.extend(
                [
                    (
                        "contextual_precision",
                        ContextualPrecisionMetric(
                            threshold=self.thresholds["contextual_precision"],
                            model=judge,
                            include_reason=self.include_reason,
                            async_mode=False,
                        ),
                    ),
                    (
                        "contextual_recall",
                        ContextualRecallMetric(
                            threshold=self.thresholds["contextual_recall"],
                            model=judge,
                            include_reason=self.include_reason,
                            async_mode=False,
                        ),
                    ),
                ]
            )
        return specs

    def score_sample(self, sample: DeepEvalSample) -> dict[str, Any]:
        from deepeval.test_case import LLMTestCase

        started = time.time()
        test_case = LLMTestCase(
            input=sample.question,
            actual_output=sample.answer,
            expected_output=sample.expected_output or None,
            retrieval_context=sample.contexts,
            metadata=sample.metadata,
        )

        metric_results: dict[str, Any] = {}
        for name, metric in self._metric_specs(sample):
            try:
                score = metric.measure(
                    test_case,
                    _show_indicator=False,
                    _log_metric_to_confident=False,
                )
                metric_results[name] = {
                    "score": float(score),
                    "threshold": self.thresholds[name],
                    "success": bool(getattr(metric, "success", score >= self.thresholds[name])),
                    "reason": str(getattr(metric, "reason", "") or ""),
                }
            except Exception as exc:
                metric_results[name] = {
                    "score": 0.0,
                    "threshold": self.thresholds[name],
                    "success": False,
                    "reason": "",
                    "error": str(exc),
                }

        scores = {
            name: result["score"]
            for name, result in metric_results.items()
            if "error" not in result
        }
        aggregate = round(_mean(list(scores.values())), 4) if scores else 0.0
        failed_metrics = [
            name
            for name, result in metric_results.items()
            if result["score"] < result["threshold"] or result.get("error")
        ]
        if aggregate < self.thresholds["aggregate"]:
            failed_metrics.append("aggregate")

        return {
            "question": sample.question,
            "case_id": sample.metadata.get("case_id", ""),
            "contract_id": sample.metadata.get("contract_id", ""),
            "scores": metric_results,
            "aggregate": aggregate,
            "passed": not failed_metrics,
            "failures": sorted(set(failed_metrics)),
            "context_count": len(sample.contexts),
            "elapsed_ms": int((time.time() - started) * 1000),
        }

    def score(self, samples: list[DeepEvalSample]) -> dict[str, Any]:
        started = time.time()
        sample_results = [self.score_sample(sample) for sample in samples]
        metric_names = sorted({
            metric
            for sample in sample_results
            for metric in sample.get("scores", {})
        })
        aggregate_scores = {
            metric: round(
                _mean([
                    sample["scores"][metric]["score"]
                    for sample in sample_results
                    if metric in sample.get("scores", {})
                ]),
                4,
            )
            for metric in metric_names
        }
        aggregate_scores["aggregate"] = round(
            _mean([sample["aggregate"] for sample in sample_results]),
            4,
        )

        failed_metrics = {
            metric: {
                "score": score,
                "threshold": self.thresholds[metric],
            }
            for metric, score in aggregate_scores.items()
            if metric in self.thresholds and score < self.thresholds[metric]
        }

        return {
            "aggregate_scores": aggregate_scores,
            "quality_gate": {
                "passed": not failed_metrics and all(sample["passed"] for sample in sample_results),
                "thresholds": self.thresholds,
                "failed_metrics": failed_metrics,
                "failed_samples": [
                    {
                        "case_id": sample["case_id"],
                        "question": sample["question"],
                        "aggregate": sample["aggregate"],
                        "failures": sample["failures"],
                    }
                    for sample in sample_results
                    if not sample["passed"]
                ],
            },
            "sample_count": len(sample_results),
            "elapsed_seconds": round(time.time() - started, 2),
            "samples": sample_results,
            "median_sample_score": (
                round(statistics.median([sample["aggregate"] for sample in sample_results]), 4)
                if sample_results
                else 0.0
            ),
        }
