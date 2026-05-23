import pytest
from unittest.mock import AsyncMock, patch

from app.evaluation.rag_evaluator import (
    DEFAULT_RAG_THRESHOLDS,
    EvalReport,
    EvalResult,
    EvalSample,
    RAGEvaluator,
)


@pytest.fixture
def evaluator():
    return RAGEvaluator()


@pytest.mark.asyncio
async def test_evaluate_sample_maps_independent_metric_scores(evaluator):
    sample = EvalSample(
        question="What is the late delivery penalty?",
        answer="The penalty is $500 per day.",
        contexts=["Section 4.1: Late delivery incurs $500/day penalty."],
        ground_truth="$500 per day late delivery penalty",
    )

    responses = [
        {"faithfulness_score": 0.91, "reasoning": "one unsupported claim"},
        {"answer_relevance_score": 0.88, "reasoning": "mostly answers"},
        {"context_precision_score": 0.75, "reasoning": "one noisy chunk"},
        {"context_recall_score": 0.67, "reasoning": "missing one reference fact"},
    ]

    with patch("app.evaluation.rag_evaluator.call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.side_effect = responses

        result = await evaluator.evaluate_sample(sample)

    assert mock_gemini.await_count == 4
    assert result.faithfulness == 0.91
    assert result.answer_relevance == 0.88
    assert result.context_precision == 0.75
    assert result.context_recall == 0.67
    assert result.aggregate_score < DEFAULT_RAG_THRESHOLDS["aggregate"]
    assert set(result.quality_failures()) == {
        "faithfulness",
        "answer_relevance",
        "context_precision",
        "context_recall",
        "aggregate",
    }


@pytest.mark.asyncio
async def test_evaluate_sample_without_ground_truth_skips_context_recall(evaluator):
    sample = EvalSample(
        question="What is the late delivery penalty?",
        answer="The penalty is $500 per day.",
        contexts=["Section 4.1: Late delivery incurs $500/day penalty."],
    )

    responses = [
        {"faithfulness_score": 1.0, "reasoning": "grounded"},
        {"answer_relevance_score": 1.0, "reasoning": "direct"},
        {"context_precision_score": 1.0, "reasoning": "all chunks useful"},
    ]

    with patch("app.evaluation.rag_evaluator.call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.side_effect = responses

        result = await evaluator.evaluate_sample(sample)

    assert mock_gemini.await_count == 3
    assert result.context_recall is None
    assert result.aggregate_score == 1.0
    assert "context_recall" not in result.metric_scores()


@pytest.mark.asyncio
async def test_evaluate_batch_reports_quality_gate_failures(evaluator):
    report = EvalReport(
        samples=[
            EvalResult(
                question="good",
                faithfulness=0.95,
                answer_relevance=0.94,
                context_recall=0.93,
                context_precision=0.92,
            ),
            EvalResult(
                question="bad",
                faithfulness=0.70,
                answer_relevance=0.80,
                context_recall=0.50,
                context_precision=0.40,
            ),
        ]
    ).finalize()

    gate = report.quality_gate()

    assert gate["passed"] is False
    assert "faithfulness" in gate["failed_metrics"]
    assert "context_precision" in gate["failed_metrics"]
    assert gate["failed_samples"][0]["question"] == "bad"
    assert set(gate["failed_samples"][0]["failures"]) >= {
        "faithfulness",
        "answer_relevance",
        "context_recall",
        "context_precision",
    }


def test_extract_score_parses_and_clamps_values():
    assert RAGEvaluator._extract_score({"faithfulness_score": "0.73"}, "faithfulness_score") == 0.73
    assert RAGEvaluator._extract_score('{"faithfulness_score": 2.5}', "faithfulness_score") == 1.0
    assert RAGEvaluator._extract_score('{"faithfulness_score": -0.5}', "faithfulness_score") == 0.0
    assert RAGEvaluator._extract_score({"faithfulness_score": "not-a-number"}, "faithfulness_score") == 0.0


def test_extract_reasoning_from_string_json():
    raw = '{"faithfulness_score": 0.5, "reasoning": "unsupported date"}'

    assert RAGEvaluator._extract_reasoning(raw) == "unsupported date"
