from app.evaluation.deepeval_eval import DeepEvalEvaluator, DeepEvalSample


class FakeMetric:
    def __init__(self, score: float, reason: str = "ok"):
        self._score = score
        self.reason = reason
        self.success = score >= 0.9

    def measure(self, test_case, **kwargs):
        self.test_case = test_case
        return self._score


def test_deepeval_score_reports_quality_gate(monkeypatch):
    def fake_specs(self, sample):
        return [
            ("answer_relevancy", FakeMetric(0.8, "too much extra text")),
            ("faithfulness", FakeMetric(1.0, "grounded")),
        ]

    monkeypatch.setattr(DeepEvalEvaluator, "_metric_specs", fake_specs)

    evaluator = DeepEvalEvaluator()
    result = evaluator.score([
        DeepEvalSample(
            question="Who are the parties?",
            answer="Provider and Customer.",
            contexts=["The Provider is CloudServe and the Customer is Enterprise Solutions."],
            expected_output="Provider is CloudServe; Customer is Enterprise Solutions.",
            metadata={"case_id": "case_1", "contract_id": "saas_agreement"},
        )
    ])

    assert result["aggregate_scores"]["answer_relevancy"] == 0.8
    assert result["aggregate_scores"]["faithfulness"] == 1.0
    assert result["aggregate_scores"]["aggregate"] == 0.9
    assert result["quality_gate"]["passed"] is False
    assert result["quality_gate"]["failed_samples"][0]["case_id"] == "case_1"
