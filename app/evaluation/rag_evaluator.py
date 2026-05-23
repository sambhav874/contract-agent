"""
RAG Evaluation framework for contract-agent.

Evaluates the quality of retrieved context and generated answers using
Gemini (no OpenAI dependency) as the judge LLM.

Metrics implemented
-------------------
1. **Faithfulness**     – Are all claims in the answer grounded in the context?
2. **Answer Relevance** – Does the answer address the question?
3. **Context Recall**   – Are ground-truth reference facts covered by context?
4. **Context Precision**– Are retrieved chunks actually useful (signal-to-noise)?

Usage
-----
    from app.evaluation.rag_evaluator import RAGEvaluator, EvalSample

    evaluator = RAGEvaluator()
    sample = EvalSample(
        question="What is the late delivery penalty?",
        answer="The penalty is $500 per day.",
        contexts=["Section 4.1: Late delivery incurs $500/day penalty."],
        ground_truth="$500 per day late delivery penalty",   # optional
    )
    result = await evaluator.evaluate_sample(sample)
    print(result.faithfulness, result.answer_relevance)
"""

from __future__ import annotations

import asyncio
import csv
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings
from app.llm.gemini_client import call_gemini


DEFAULT_RAG_THRESHOLDS = {
    "faithfulness": 0.92,
    "answer_relevance": 0.90,
    "context_recall": 0.90,
    "context_precision": 0.90,
    "aggregate": 0.90,
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class EvalSample:
    """A single RAG evaluation sample."""
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str = ""          # Optional reference answer
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Evaluation scores for a single sample (all 0–1, higher = better)."""
    question: str
    faithfulness: float = 0.0
    answer_relevance: float = 0.0
    context_recall: float | None = None
    context_precision: float = 0.0
    # Raw judge reasoning (for debugging)
    faithfulness_reason: str = ""
    answer_relevance_reason: str = ""
    context_recall_reason: str = ""
    context_precision_reason: str = ""
    error: str = ""

    @property
    def aggregate_score(self) -> float:
        """Weighted aggregate across metrics that are available for this sample."""
        weighted = [
            ("faithfulness", self.faithfulness, 0.35),
            ("answer_relevance", self.answer_relevance, 0.25),
            ("context_precision", self.context_precision, 0.20),
        ]
        if self.context_recall is not None:
            weighted.append(("context_recall", self.context_recall, 0.20))

        total_weight = sum(weight for _, _, weight in weighted)
        if total_weight == 0:
            return 0.0
        return round(sum(score * weight for _, score, weight in weighted) / total_weight, 4)

    def metric_scores(self) -> dict[str, float]:
        scores = {
            "faithfulness": self.faithfulness,
            "answer_relevance": self.answer_relevance,
            "context_precision": self.context_precision,
            "aggregate": self.aggregate_score,
        }
        if self.context_recall is not None:
            scores["context_recall"] = self.context_recall
        return scores

    def quality_failures(self, thresholds: dict[str, float] | None = None) -> list[str]:
        thresholds = thresholds or DEFAULT_RAG_THRESHOLDS
        scores = self.metric_scores()
        return [
            metric
            for metric, threshold in thresholds.items()
            if metric in scores and scores[metric] < threshold
        ]


@dataclass
class EvalReport:
    """Aggregate evaluation report across multiple samples."""
    samples: list[EvalResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    # Computed aggregates (populated by finalize())
    mean_faithfulness: float = 0.0
    mean_answer_relevance: float = 0.0
    mean_context_recall: float = 0.0
    mean_context_precision: float = 0.0
    mean_aggregate: float = 0.0

    def finalize(self) -> "EvalReport":
        """Compute mean scores across all samples."""
        n = len(self.samples)
        if n == 0:
            return self
        self.mean_faithfulness      = round(sum(s.faithfulness for s in self.samples) / n, 4)
        self.mean_answer_relevance  = round(sum(s.answer_relevance for s in self.samples) / n, 4)
        recall_scores = [s.context_recall for s in self.samples if s.context_recall is not None]
        self.mean_context_recall    = round(sum(recall_scores) / len(recall_scores), 4) if recall_scores else 0.0
        self.mean_context_precision = round(sum(s.context_precision for s in self.samples) / n, 4)
        self.mean_aggregate         = round(sum(s.aggregate_score for s in self.samples) / n, 4)
        return self

    def quality_gate(self, thresholds: dict[str, float] | None = None) -> dict[str, Any]:
        """Return a deterministic pass/fail gate for 90+ style quality targets."""
        thresholds = thresholds or DEFAULT_RAG_THRESHOLDS
        metrics = {
            "faithfulness": self.mean_faithfulness,
            "answer_relevance": self.mean_answer_relevance,
            "context_precision": self.mean_context_precision,
            "aggregate": self.mean_aggregate,
        }
        if any(sample.context_recall is not None for sample in self.samples):
            metrics["context_recall"] = self.mean_context_recall

        failed_metrics = {
            metric: {"score": score, "threshold": thresholds[metric]}
            for metric, score in metrics.items()
            if metric in thresholds and score < thresholds[metric]
        }

        failed_samples = [
            {
                "question": sample.question,
                "failures": sample.quality_failures(thresholds),
                "scores": sample.metric_scores(),
            }
            for sample in self.samples
            if sample.quality_failures(thresholds)
        ]

        return {
            "passed": not failed_metrics and not failed_samples,
            "thresholds": thresholds,
            "metrics": metrics,
            "failed_metrics": failed_metrics,
            "failed_samples": failed_samples,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean_faithfulness": self.mean_faithfulness,
            "mean_answer_relevance": self.mean_answer_relevance,
            "mean_context_recall": self.mean_context_recall,
            "mean_context_precision": self.mean_context_precision,
            "mean_aggregate": self.mean_aggregate,
            "num_samples": len(self.samples),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "quality_gate": self.quality_gate(),
            "samples": [
                {
                    "question": s.question,
                    "faithfulness": s.faithfulness,
                    "answer_relevance": s.answer_relevance,
                    "context_recall": s.context_recall,
                    "context_precision": s.context_precision,
                    "aggregate": s.aggregate_score,
                    "error": s.error,
                }
                for s in self.samples
            ],
        }


# ── Evaluator ─────────────────────────────────────────────────────────────────

class RAGEvaluator:
    """
    Gemini-powered RAG evaluator.

    Uses ``gemini-3.1-flash-lite-preview`` (fast, cheap) as the judge by default.
    Set ``judge_model`` to switch to a stronger model if needed.
    """

    def __init__(self, judge_model: str | None = None):
        self.judge_model = judge_model or settings.gemini_fast_model

    # ── Public API ───────────────────────────────────────────────────────

    async def evaluate_sample(self, sample: EvalSample) -> EvalResult:
        """Evaluate a single RAG sample across all four metrics."""
        result = EvalResult(question=sample.question)
        context_block = self._format_contexts(sample.contexts)

        tasks = [
            self._score_faithfulness(sample.answer, context_block),
            self._score_answer_relevance(sample.question, sample.answer),
            self._score_context_precision(sample.question, sample.contexts),
        ]

        # context_recall only makes sense when ground truth is provided
        if sample.ground_truth:
            tasks.append(self._score_context_recall(sample.ground_truth, context_block))

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            result.error = str(e)
            return result

        # Unpack in order
        _faith = results[0]
        _rel   = results[1]
        _prec  = results[2]
        _rec   = results[3] if sample.ground_truth and len(results) > 3 else None

        if isinstance(_faith, Exception):
            result.faithfulness_reason = f"ERROR: {_faith}"
        else:
            result.faithfulness, result.faithfulness_reason = _faith  # type: ignore[misc]

        if isinstance(_rel, Exception):
            result.answer_relevance_reason = f"ERROR: {_rel}"
        else:
            result.answer_relevance, result.answer_relevance_reason = _rel  # type: ignore[misc]

        if isinstance(_prec, Exception):
            result.context_precision_reason = f"ERROR: {_prec}"
        else:
            result.context_precision, result.context_precision_reason = _prec  # type: ignore[misc]

        if _rec is not None:
            if isinstance(_rec, Exception):
                result.context_recall_reason = f"ERROR: {_rec}"
            else:
                result.context_recall, result.context_recall_reason = _rec  # type: ignore[misc]

        return result

    async def evaluate_batch(
        self,
        samples: list[EvalSample],
        concurrency: int = 3,
    ) -> EvalReport:
        """Evaluate a batch of samples with bounded concurrency."""
        t0 = time.perf_counter()
        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded(sample: EvalSample) -> EvalResult:
            async with semaphore:
                return await self.evaluate_sample(sample)

        results = await asyncio.gather(*[_bounded(s) for s in samples])
        report = EvalReport(
            samples=list(results),
            elapsed_seconds=time.perf_counter() - t0,
        )
        return report.finalize()

    async def evaluate_from_csv(
        self,
        csv_path: str,
        contract_id: str,
        top_k: int = 10,
        max_samples: int | None = None,
    ) -> EvalReport:
        """
        Build evaluation samples from a KPI CSV file and run evaluation.

        The CSV is expected to have at least a 'name' and 'value' column
        (format used by ``exhaustive_kpis.csv``).  Each row becomes one
        EvalSample where:
          - question = "What is the <name> KPI?"
          - answer   = retrieved & formatted context (simulated answer)
          - contexts = chunks from hybrid retrieval
          - ground_truth = "<value> <unit>"
        """
        samples = await self._build_samples_from_csv(
            csv_path, contract_id, top_k, max_samples
        )
        return await self.evaluate_batch(samples)

    # ── Individual metric scorers ────────────────────────────────────────

    async def _score_faithfulness(
        self, answer: str, context: str
    ) -> tuple[float, str]:
        """
        Score faithfulness: fraction of answer claims that are grounded in context.

        Prompt asks Gemini to list all claims in the answer, then check each
        against the context.  Returns a ratio [0, 1].
        """
        prompt = f"""You are a strict factual grounding evaluator.

CONTEXT (retrieved contract chunks):
{context[:6000]}

ANSWER TO EVALUATE:
{answer}

Task:
1. List every factual claim made in the ANSWER (numbered list).
2. For each claim, state whether it is SUPPORTED or UNSUPPORTED by the CONTEXT.
3. Calculate: faithfulness_score = supported_claims / total_claims  (round to 2dp)

Respond as JSON:
{{
  "claims": [
    {{"claim": "...", "supported": true}},
    ...
  ],
  "faithfulness_score": 0.95,
  "reasoning": "Brief explanation"
}}"""

        raw = await call_gemini(
            model=self.judge_model,
            system_prompt="You are an expert RAG evaluation judge. Respond only with valid JSON.",
            user_message=prompt,
            temperature=0.0,
        )
        return self._extract_score(raw, "faithfulness_score"), self._extract_reasoning(raw)

    async def _score_answer_relevance(
        self, question: str, answer: str
    ) -> tuple[float, str]:
        """
        Score answer relevance: does the answer actually address the question?
        Uses reverse-generation: generate likely questions from the answer, compute
        cosine similarity with the original question via Gemini's judgement.
        """
        prompt = f"""You are evaluating whether an answer is relevant to a question.

QUESTION: {question}

ANSWER: {answer}

Task:
1. Generate 3 questions that the ANSWER most directly addresses.
2. Rate how well the ANSWER addresses the original QUESTION on a scale 0–1.
   - 1.0 = fully addresses the question
   - 0.0 = completely off-topic

Respond as JSON:
{{
  "generated_questions": ["...", "...", "..."],
  "answer_relevance_score": 0.87,
  "reasoning": "Brief explanation"
}}"""

        raw = await call_gemini(
            model=self.judge_model,
            system_prompt="You are an expert RAG evaluation judge. Respond only with valid JSON.",
            user_message=prompt,
            temperature=0.0,
        )
        return self._extract_score(raw, "answer_relevance_score"), self._extract_reasoning(raw)

    async def _score_context_recall(
        self, ground_truth: str, context: str
    ) -> tuple[float, str]:
        """
        Score context recall: are the ground-truth facts present in the retrieved context?
        """
        prompt = f"""You are evaluating whether retrieved context contains the necessary information.

REFERENCE ANSWER (ground truth):
{ground_truth}

RETRIEVED CONTEXT:
{context[:6000]}

Task:
1. Identify each key fact/claim in the REFERENCE ANSWER.
2. For each fact, state if it can be attributed to the CONTEXT.
3. context_recall_score = facts_found_in_context / total_facts_in_reference  (round to 2dp)

Respond as JSON:
{{
  "reference_facts": [
    {{"fact": "...", "found_in_context": true}},
    ...
  ],
  "context_recall_score": 0.80,
  "reasoning": "Brief explanation"
}}"""

        raw = await call_gemini(
            model=self.judge_model,
            system_prompt="You are an expert RAG evaluation judge. Respond only with valid JSON.",
            user_message=prompt,
            temperature=0.0,
        )
        return self._extract_score(raw, "context_recall_score"), self._extract_reasoning(raw)

    async def _score_context_precision(
        self, question: str, contexts: list[str]
    ) -> tuple[float, str]:
        """
        Score context precision: what fraction of retrieved chunks are actually relevant?
        Measures signal-to-noise ratio and ranking quality of the retrieval.
        """
        labeled = "\n\n".join(
            f"[CHUNK {i+1}]\n{c[:800]}" for i, c in enumerate(contexts)
        )
        prompt = f"""You are evaluating the precision of retrieved context for a question.

QUESTION: {question}

RETRIEVED CHUNKS:
{labeled}

Task:
For each chunk, decide if it is RELEVANT or IRRELEVANT to answering the question.
Then calculate rank-aware context precision:
- precision@k = relevant_chunks_seen_up_to_rank_k / k
- context_precision_score = average precision@k over ranks where the chunk is relevant
- if no chunks are relevant, context_precision_score = 0.0

Respond as JSON:
{{
  "chunks": [
    {{"chunk": 1, "relevant": true, "reason": "..."}},
    ...
  ],
  "context_precision_score": 0.75,
  "reasoning": "Overall explanation"
}}"""

        raw = await call_gemini(
            model=self.judge_model,
            system_prompt="You are an expert RAG evaluation judge. Respond only with valid JSON.",
            user_message=prompt,
            temperature=0.0,
        )
        return self._extract_score(raw, "context_precision_score"), self._extract_reasoning(raw)

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_contexts(contexts: list[str]) -> str:
        return "\n\n".join(
            f"[CHUNK {i+1}]\n{c}" for i, c in enumerate(contexts)
        )

    @staticmethod
    def _extract_score(raw: dict[str, Any], key: str) -> float:
        """Safely extract a numeric score from a Gemini JSON response."""
        value: Any = None
        if isinstance(raw, dict):
            value = raw.get(key)
        else:
            raw_str = str(raw)
            match = re.search(rf'"{re.escape(key)}"\s*:\s*([0-9.]+)', raw_str)
            if match:
                value = match.group(1)

        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))

    @staticmethod
    def _extract_reasoning(raw: dict[str, Any]) -> str:
        """Extract reasoning field from response."""
        if isinstance(raw, dict):
            return str(raw.get("reasoning", ""))
        try:
            data = json.loads(str(raw))
            if isinstance(data, dict):
                return str(data.get("reasoning", ""))
        except Exception:
            pass
        return ""

    async def _build_samples_from_csv(
        self,
        csv_path: str,
        contract_id: str,
        top_k: int,
        max_samples: int | None,
    ) -> list[EvalSample]:
        """Build EvalSample list from a KPI CSV file + live retrieval."""
        from app.retrieval.langchain_retriever import get_langchain_retriever

        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        rows: list[dict[str, str]] = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
                if max_samples and len(rows) >= max_samples:
                    break

        retriever = get_langchain_retriever(
            contract_id=contract_id,
            top_k=top_k,
        )

        samples: list[EvalSample] = []
        for row in rows:
            name  = row.get("name", row.get("KPI Name", ""))
            value = row.get("value", row.get("Value", ""))
            unit  = row.get("unit", row.get("Unit", ""))
            if not name:
                continue

            question = f"What is the {name} KPI or metric in this contract?"
            ground_truth = f"{value} {unit}".strip()

            # Retrieve context chunks via LangChain retriever
            docs = await retriever._aget_relevant_documents(question)
            contexts = [d.page_content for d in docs]

            # Simulated answer: concatenate top chunks (evaluates retrieval quality)
            answer = "\n".join(contexts[:3]) if contexts else "(no context retrieved)"

            samples.append(EvalSample(
                question=question,
                answer=answer,
                contexts=contexts,
                ground_truth=ground_truth,
                metadata=row,
            ))

        return samples
