"""Full backend evaluation harness for contract-agent.

This evaluator intentionally excludes generated UI validation. It focuses on:
- ChatAgent orchestration
- intent routing
- specialist agent selection
- tool selection and tool output quality
- retrieval/evidence coverage
- factual value extraction
- citations/section grounding
- latency and failure behavior
- optional RAGAS grounding metrics

Run:
    python -m app.evaluation.full_evaluator
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.agents.chat_agent import ChatAgent
from app.agents.clause_agent import ClauseAgent
from app.agents.kpi_agent import KPIAgent
from app.agents.obligation_agent import ObligationAgent
from app.agents.redflag_agent import RedFlagAgent
from app.agents.risk_agent import RiskAgent
from app.agents.summary_agent import SummaryAgent
from app.db.mongodb import MongoDB
from app.ingestion.chunker import hierarchical_chunk
from app.ingestion.embedder import get_embedding_service
from app.ingestion.parser import parse_contract
from app.routing.intent_router import route_intent


DEFAULT_CASES = "tests/evaluation/cases/golden_cases.json"
DEFAULT_OUTPUT = "reports/evaluation/evaluation_results_full.json"
DEFAULT_FAILURES = "reports/evaluation/evaluation_failures.json"
DEFAULT_REPORT = "docs/reports/EVALUATION_FULL_REPORT.md"

AGENT_CLASSES = {
    "KPIAgent": KPIAgent,
    "RiskAgent": RiskAgent,
    "ClauseAgent": ClauseAgent,
    "ObligationAgent": ObligationAgent,
    "SummaryAgent": SummaryAgent,
    "RedFlagAgent": RedFlagAgent,
}

CHAT_WEIGHTS = {
    "factual_accuracy": 0.25,
    "retrieval_citation": 0.20,
    "completeness": 0.15,
    "routing": 0.15,
    "structured_calculation": 0.10,
    "failure_behavior": 0.075,
    "latency": 0.075,
}


@dataclass
class LayerResult:
    """One evaluated layer for one case."""

    status: str = "skipped"
    score: float = 0.0
    scores: dict[str, float] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    latency_ms: int = 0


def _json_default(value: Any) -> str:
    return str(value)


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2265": ">=",
        "\u2264": "<=",
        "\u00d7": "x",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = text.replace(",", "")
    text = text.replace("usd", "$")
    text = re.sub(r"\bfive[-\s]?year\b", "5 year", text)
    text = re.sub(r"\bthree[-\s]?year\b", "3 year", text)
    text = re.sub(r"\bthirty\b", "30", text)
    text = re.sub(r"\bone hundred eighty\b", "180", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokens_for_value(value: str) -> list[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []

    # For ranges such as "$28.50-$42.00" or "2.5%-8.0%", accept endpoint evidence.
    if "-" in normalized:
        endpoints = [p.strip() for p in normalized.split("-") if p.strip()]
        if len(endpoints) >= 2:
            return endpoints[:2]

    if "/" in normalized and re.search(r"\d", normalized):
        return [p.strip() for p in normalized.split("/") if p.strip()]

    return [normalized]


def _contains_value(haystack: str, expected: str) -> bool:
    text = _normalize_text(haystack)
    expected_norm = _normalize_text(expected)
    if not expected_norm:
        return True
    if expected_norm in text:
        return True

    tokens = _tokens_for_value(expected)
    if len(tokens) > 1 and all(token in text for token in tokens):
        return True

    # Accept "$5000" when expected was "$5,000".
    money = re.sub(r"[^0-9.]", "", expected_norm)
    if "$" in expected_norm and money and money in text:
        return True

    return False


def _coverage_score(expected: list[str] | dict[str, str], actual_text: str) -> tuple[float, list[str], list[str]]:
    if isinstance(expected, dict):
        items = [f"{key}={value}" for key, value in expected.items()]
        values = list(expected.values())
    else:
        items = list(expected or [])
        values = items

    if not values:
        return 1.0, [], []

    found = []
    missing = []
    for label, value in zip(items, values):
        if _contains_value(actual_text, str(value)):
            found.append(label)
        else:
            missing.append(label)
    return len(found) / len(values), found, missing


def _section_score(expected_sections: list[str], actual_text: str) -> tuple[float, list[str], list[str]]:
    return _coverage_score(expected_sections, actual_text)


def _latency_score(latency_ms: int) -> float:
    seconds = latency_ms / 1000
    if seconds <= 30:
        return 1.0
    if seconds <= 90:
        return 0.75
    if seconds <= 180:
        return 0.45
    if seconds <= 300:
        return 0.20
    return 0.05


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _score_weighted(scores: dict[str, float], weights: dict[str, float]) -> float:
    total_weight = 0.0
    total_score = 0.0
    for name, weight in weights.items():
        if name in scores:
            total_weight += weight
            total_score += scores[name] * weight
    return total_score / total_weight if total_weight else 0.0


def _extract_selected_agent(chunks: list[dict[str, Any]]) -> str:
    for chunk in chunks:
        if chunk.get("type") != "thought":
            continue
        content = str(chunk.get("content", ""))
        match = re.search(r"Delegating to\s+([A-Za-z0-9_]+)", content)
        if match:
            return match.group(1)
    return ""


def _extract_citations(text: str) -> list[str]:
    citations = set()
    for match in re.findall(r"\[(Section\s+[^\]]+|Article\s+[^\]]+|CHUNK:\s*[^\]]+)\]", text, flags=re.IGNORECASE):
        citations.add(match.strip())
    for match in re.findall(r"\b(Section\s+\d+(?:\.\d+)?)\b", text, flags=re.IGNORECASE):
        citations.add(match.strip())
    for match in re.findall(r"\b(Article\s+[IVXLC]+)\b", text, flags=re.IGNORECASE):
        citations.add(match.strip())
    return sorted(citations)


def _has_internal_error(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in [
            "unsupported argument",
            "traceback",
            "internal error",
            "technical error",
            "tool_execution_failed",
            "stream error",
            "classification error",
        ]
    )


def _is_false_negative(case: dict[str, Any], answer: str) -> bool:
    lowered = _normalize_text(answer)
    expected_keywords = case.get("expected_keywords", [])
    if not expected_keywords:
        return False
    denial_phrases = [
        "no reporting obligations",
        "no obligations",
        "does not contain",
        "not specified",
        "i don't have that information",
        "unable to provide",
        "no data was retrieved",
    ]
    return any(phrase in lowered for phrase in denial_phrases)


def _failure_tags(
    case: dict[str, Any],
    trace: dict[str, Any],
    scores: dict[str, float],
    answer: str,
) -> list[str]:
    tags: list[str] = []
    if scores.get("intent_score", 1.0) < 1.0:
        tags.append("intent_mismatch")
    if scores.get("agent_score", 1.0) < 1.0:
        tags.append("wrong_agent")
    if scores.get("compound_score", 1.0) < 1.0:
        tags.append("compound_routing_mismatch")
    if scores.get("tool_selection_score", 1.0) < 1.0:
        tags.append("wrong_tool")
    if scores.get("retrieval_score", 1.0) < 0.8:
        tags.append("retrieval_miss")
    if scores.get("citation_score", 1.0) < 0.8:
        tags.append("missing_citation")
    if scores.get("value_score", 1.0) < 0.8:
        tags.append("wrong_value")
    if scores.get("keyword_score", 1.0) < 0.8:
        tags.append("incomplete_answer")
    if _has_internal_error(answer):
        tags.append("tool_error")
    if _is_false_negative(case, answer):
        tags.append("false_negative")
    if trace.get("latency_ms", 0) > 180_000:
        tags.append("timeout")
    if trace.get("errors"):
        tags.append("runtime_error")
    return sorted(set(tags))


def _stringify(data: Any) -> str:
    return json.dumps(data, default=_json_default, sort_keys=True)


def _collect_context_strings(value: Any, output: list[str]) -> None:
    """Extract candidate retrieved context strings from nested tool result data."""
    if value is None:
        return
    if isinstance(value, str):
        text = value.strip()
        if len(text) >= 40:
            output.append(text)
        return
    if isinstance(value, list):
        for item in value:
            _collect_context_strings(item, output)
        return
    if isinstance(value, dict):
        for key in (
            "text",
            "overview",
            "summary_markdown",
            "context",
            "quote",
            "exact_quote",
            "clause_text",
        ):
            if key in value:
                _collect_context_strings(value.get(key), output)
        for nested_key in ("data", "results", "chunks", "clauses", "details"):
            if nested_key in value:
                _collect_context_strings(value.get(nested_key), output)


def _contexts_from_chat_trace(trace: dict[str, Any], limit: int = 12) -> list[str]:
    """Build RAGAS contexts from actual ChatAgent tool_result events."""
    contexts: list[str] = []
    seen: set[str] = set()

    for tool_result in trace.get("tool_results", []) or []:
        raw_content = tool_result.get("content")
        parsed: Any = raw_content
        if isinstance(raw_content, str):
            try:
                parsed = json.loads(raw_content)
            except Exception:
                parsed = raw_content

        before = len(contexts)
        _collect_context_strings(parsed, contexts)
        if len(contexts) == before and isinstance(raw_content, str) and raw_content.strip():
            _collect_context_strings(raw_content, contexts)

    deduped = []
    for context in contexts:
        normalized = _normalize_text(context[:1000])
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(context)
        if len(deduped) >= limit:
            break
    return deduped


class FullEvaluator:
    """Runs full backend evaluation cases."""

    def __init__(
        self,
        cases: list[dict[str, Any]],
        layers: set[str],
        ingest: bool = False,
        seed_kpis: bool = False,
        skip_preflight: bool = False,
        chat_timeout_s: int = 180,
        tool_timeout_s: int = 60,
        agent_timeout_s: int = 180,
        max_cases: int | None = None,
        case_ids: set[str] | None = None,
    ):
        self.layers = layers
        self.ingest = ingest
        self.seed_kpis = seed_kpis
        self.skip_preflight = skip_preflight
        self.chat_timeout_s = chat_timeout_s
        self.tool_timeout_s = tool_timeout_s
        self.agent_timeout_s = agent_timeout_s
        self.case_ids = case_ids or set()
        selected = [case for case in cases if not self.case_ids or case.get("id") in self.case_ids]
        self.cases = selected[:max_cases] if max_cases else selected

    async def run(self) -> dict[str, Any]:
        started = time.time()
        await MongoDB.connect()
        if self.ingest:
            await self._ingest_contracts()
        if self.seed_kpis:
            await self._seed_kpi_registry()

        preflight = await self._preflight_chunks()
        if not self.skip_preflight and not preflight["passed"]:
            details = "; ".join(
                f"{item['contract_id']}: total={item['total_chunks']}, levels={item['levels']}"
                for item in preflight["contracts"]
                if item["status"] != "ok"
            )
            raise RuntimeError(
                "Evaluation preflight failed: selected contracts are missing retrievable chunks. "
                "Rerun with --ingest, or use --skip-preflight only for debugging. "
                f"Details: {details}"
            )

        results = []
        for case in self.cases:
            print(f"[full-eval] Running {case['id']} ({case.get('category', 'uncategorized')})")
            results.append(await self.evaluate_case(case))

        return {
            "version": 1,
            "timestamp": datetime.now().isoformat(),
            "layers": sorted(self.layers),
            "total_cases": len(results),
            "duration_ms": int((time.time() - started) * 1000),
            "preflight": preflight,
            "results": results,
            "summary": self._summarize(results),
        }

    async def _preflight_chunks(self) -> dict[str, Any]:
        """Verify that every selected contract has chunks before evaluation starts."""
        contract_ids = sorted({case["contract_id"] for case in self.cases if case.get("contract_id")})
        chunks = MongoDB.get_collection("chunks")
        contracts = []

        for contract_id in contract_ids:
            levels: dict[str, int] = {}
            for level in ("macro", "meso", "micro"):
                levels[level] = await chunks.count_documents({
                    "contract_id": contract_id,
                    "chunk_level": level,
                })
            total_chunks = sum(levels.values())
            retrievable_chunks = levels["macro"] + levels["meso"] + levels["micro"]
            status = "ok" if total_chunks > 0 and retrievable_chunks > 0 else "missing_chunks"
            contracts.append({
                "contract_id": contract_id,
                "total_chunks": total_chunks,
                "levels": levels,
                "status": status,
            })

        passed = all(item["status"] == "ok" for item in contracts)
        if passed:
            print(
                "[full-eval] Preflight chunks OK: "
                + ", ".join(f"{item['contract_id']}={item['total_chunks']}" for item in contracts)
            )
        else:
            print(
                "[full-eval] Preflight chunks FAILED: "
                + ", ".join(
                    f"{item['contract_id']}={item['total_chunks']} {item['levels']}"
                    for item in contracts
                    if item["status"] != "ok"
                )
            )
        return {"passed": passed, "contracts": contracts}

    async def _ingest_contracts(self) -> None:
        unique_contracts: dict[str, dict[str, str]] = {}
        for case in self.cases:
            contract_file = case.get("contract_file")
            contract_name = case.get("contract_name") or Path(contract_file or "").stem
            if contract_file:
                unique_contracts[contract_file] = {
                    "contract_file": contract_file,
                    "contract_name": contract_name,
                }

        for info in unique_contracts.values():
            contract_file = info["contract_file"]
            contract_name = info["contract_name"]
            print(f"[full-eval] Ingesting {contract_file}")
            metadata, structural_map, text = await parse_contract(contract_file, contract_name)
            chunks = hierarchical_chunk(text, metadata.contract_id, structural_map)
            embedder = get_embedding_service()
            chunks = await embedder.embed_chunks(chunks)
            await MongoDB.delete_contract(metadata.contract_id)
            await MongoDB.insert_contract(metadata)
            await MongoDB.insert_chunks(chunks)

    async def _seed_kpi_registry(self) -> None:
        unique_contract_ids = sorted({case["contract_id"] for case in self.cases if case.get("contract_id")})
        for contract_id in unique_contract_ids:
            print(f"[full-eval] Seeding KPI registry for {contract_id}")
            query = (
                "Extract all KPIs, SLA targets, thresholds, penalties, remediation steps, "
                "pricing metrics, payment terms, reporting deadlines, and key dates."
            )
            query_plan = await route_intent("KPI_QUERY", user_query=query)
            output = await KPIAgent().analyze(query_plan, contract_id, query)
            kpis = [kpi.model_dump() for kpi in output.kpis]
            if kpis:
                await MongoDB.upsert_kpis(contract_id, kpis)

    async def evaluate_case(self, case: dict[str, Any]) -> dict[str, Any]:
        result = {
            "id": case["id"],
            "category": case.get("category", ""),
            "contract_id": case.get("contract_id", ""),
            "query": case["query"],
            "expected": {
                "intent": case.get("expected_intent"),
                "agent": case.get("expected_agent"),
                "tools": case.get("expected_tools", []),
                "sections": case.get("expected_sections", []),
                "keywords": case.get("expected_keywords", []),
                "values": case.get("expected_values", {}),
            },
            "layers": {},
            "overall_score": 0.0,
            "failures": [],
        }

        layer_scores: list[float] = []

        if "chat" in self.layers:
            chat = await self._run_layer_with_timeout("chat", self.evaluate_chat(case), self.chat_timeout_s)
            result["layers"]["chat"] = chat.__dict__
            layer_scores.append(chat.score)

        if "tools" in self.layers:
            tools = await self._run_layer_with_timeout("tools", self.evaluate_tools(case), self.tool_timeout_s)
            result["layers"]["tools"] = tools.__dict__
            layer_scores.append(tools.score)

        if "agents" in self.layers:
            agents = await self._run_layer_with_timeout("agents", self.evaluate_agent(case), self.agent_timeout_s)
            result["layers"]["agents"] = agents.__dict__
            layer_scores.append(agents.score)

        result["overall_score"] = _mean(layer_scores)
        failures = []
        for layer_name, layer_result in result["layers"].items():
            for failure in layer_result.get("failures", []):
                failures.append(f"{layer_name}:{failure}")
        result["failures"] = sorted(set(failures))
        return result

    async def _run_layer_with_timeout(
        self,
        layer_name: str,
        coro: Any,
        timeout_s: int,
    ) -> LayerResult:
        started = time.time()
        try:
            return await asyncio.wait_for(coro, timeout=timeout_s)
        except asyncio.TimeoutError:
            latency_ms = int((time.time() - started) * 1000)
            return LayerResult(
                status="failed",
                score=0.0,
                scores={"timeout": 0.0},
                failures=["timeout"],
                trace={
                    "layer": layer_name,
                    "timeout_seconds": timeout_s,
                    "message": f"{layer_name} evaluation exceeded {timeout_s}s timeout.",
                },
                error=f"{layer_name} evaluation exceeded {timeout_s}s timeout.",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.time() - started) * 1000)
            return LayerResult(
                status="failed",
                score=0.0,
                scores={"runtime_error": 0.0},
                failures=["runtime_error"],
                trace={
                    "layer": layer_name,
                    "exception": str(exc),
                    "traceback": traceback.format_exc(),
                },
                error=str(exc),
                latency_ms=latency_ms,
            )

    async def evaluate_chat(self, case: dict[str, Any]) -> LayerResult:
        started = time.time()
        chunks: list[dict[str, Any]] = []
        answer_parts: list[str] = []
        errors: list[str] = []
        intent = ""
        intent_metadata: dict[str, Any] = {}
        tools_called: list[str] = []
        tool_results: list[dict[str, Any]] = []

        try:
            agent = ChatAgent(case["contract_id"])
            session_id = f"eval_{case['id']}_{int(time.time())}"
            async for chunk in agent.answer_question_stream(case["query"], session_id=session_id):
                chunks.append(chunk)
                chunk_type = chunk.get("type")
                if chunk_type == "intent":
                    intent = chunk.get("intent", "")
                    intent_metadata = {
                        "confidence": chunk.get("confidence"),
                        "reasoning": chunk.get("reasoning"),
                        "needs_contract_context": chunk.get("needs_contract_context"),
                        "needs_structured_data": chunk.get("needs_structured_data"),
                        "is_compound": chunk.get("is_compound"),
                    }
                elif chunk_type == "content":
                    answer_parts.append(chunk.get("content", ""))
                elif chunk_type == "tool_call":
                    tools_called.append(chunk.get("name", ""))
                elif chunk_type == "tool_result":
                    tool_results.append(chunk)
                elif chunk_type == "error":
                    errors.append(chunk.get("content", ""))
        except Exception as exc:
            errors.append(str(exc))
            chunks.append({"type": "exception", "content": traceback.format_exc()})

        latency_ms = int((time.time() - started) * 1000)
        answer = "".join(answer_parts)
        selected_agent = _extract_selected_agent(chunks)
        trace = {
            "intent": intent,
            "intent_metadata": intent_metadata,
            "selected_agent": selected_agent,
            "tools_called": tools_called,
            "tool_results": tool_results,
            "chunks": chunks,
            "answer": answer,
            "citations": _extract_citations(answer),
            "errors": errors,
            "latency_ms": latency_ms,
        }

        scores: dict[str, float] = {}
        expected_intent = case.get("expected_intent")
        if expected_intent:
            scores["intent_score"] = 1.0 if intent == expected_intent else 0.0

        expected_agent = case.get("expected_agent")
        if expected_agent:
            scores["agent_score"] = 1.0 if selected_agent == expected_agent else 0.0

        if "expected_is_compound" in case:
            actual_is_compound = bool(intent_metadata.get("is_compound"))
            scores["compound_score"] = 1.0 if actual_is_compound == bool(case["expected_is_compound"]) else 0.0

        expected_tools = case.get("expected_tools") or []
        if expected_tools:
            called = set(tools_called)
            scores["tool_selection_score"] = len(called.intersection(expected_tools)) / len(expected_tools)

        keyword_score, found_keywords, missing_keywords = _coverage_score(case.get("expected_keywords", []), answer)
        value_score, found_values, missing_values = _coverage_score(case.get("expected_values", {}), answer)
        citation_score, found_sections, missing_sections = _section_score(case.get("expected_sections", []), answer)

        evidence_blob = answer + "\n" + _stringify(tool_results)
        retrieval_score, evidence_sections_found, evidence_sections_missing = _section_score(
            case.get("expected_sections", []),
            evidence_blob,
        )

        scores["keyword_score"] = keyword_score
        scores["value_score"] = value_score
        scores["factual_accuracy"] = _mean([keyword_score, value_score])
        scores["completeness"] = _mean([keyword_score, value_score, citation_score])
        scores["citation_score"] = citation_score
        scores["retrieval_score"] = retrieval_score
        scores["retrieval_citation"] = _mean([retrieval_score, citation_score])
        scores["routing"] = _mean([
            scores.get("intent_score", 1.0),
            scores.get("agent_score", 1.0),
            scores.get("compound_score", 1.0),
            scores.get("tool_selection_score", 1.0),
        ])
        scores["structured_calculation"] = 1.0
        if case.get("category") == "compliance" and expected_tools:
            scores["structured_calculation"] = scores.get("tool_selection_score", 0.0)
        scores["failure_behavior"] = 0.0 if errors or _has_internal_error(answer) or _is_false_negative(case, answer) else 1.0
        scores["latency"] = _latency_score(latency_ms)

        failures = _failure_tags(case, trace, scores, answer)
        trace["found_keywords"] = found_keywords
        trace["missing_keywords"] = missing_keywords
        trace["found_values"] = found_values
        trace["missing_values"] = missing_values
        trace["found_sections"] = found_sections
        trace["missing_sections"] = missing_sections
        trace["evidence_sections_found"] = evidence_sections_found
        trace["evidence_sections_missing"] = evidence_sections_missing

        score = _score_weighted(scores, CHAT_WEIGHTS)
        status = "passed" if score >= 0.80 and not failures else "failed"
        return LayerResult(status=status, score=score, scores=scores, failures=failures, trace=trace, latency_ms=latency_ms)

    async def evaluate_tools(self, case: dict[str, Any]) -> LayerResult:
        started = time.time()
        checks = case.get("tool_checks") or []
        expected_tools = case.get("expected_tools") or []
        if not checks and expected_tools:
            checks = [{"tool": tool, "args": {}} for tool in expected_tools]
        if not checks:
            return LayerResult(status="skipped", score=1.0, scores={}, trace={"reason": "no tool checks"})

        agent = ChatAgent(case["contract_id"])
        tool_results = []
        scores = []
        failures: list[str] = []

        for check in checks:
            tool_name = check["tool"]
            args = check.get("args", {})
            started_tool = time.time()
            raw = await agent.tool_registry.execute(tool_name, **args)
            duration_ms = int((time.time() - started_tool) * 1000)
            data_text = _stringify(raw.data)

            keyword_score, _, missing_keywords = _coverage_score(check.get("expected_keywords", []), data_text)
            section_score, _, missing_sections = _section_score(check.get("expected_sections", []), data_text)
            success_score = 1.0 if raw.success else 0.0
            score = _mean([success_score, keyword_score, section_score])
            scores.append(score)

            check_failures = []
            if not raw.success:
                check_failures.append("tool_error")
            if keyword_score < 0.8:
                check_failures.append("tool_missing_keywords")
            if section_score < 0.8:
                check_failures.append("tool_retrieval_miss")
            failures.extend(f"{tool_name}:{failure}" for failure in check_failures)

            tool_results.append({
                "tool": tool_name,
                "args": args,
                "success": raw.success,
                "metadata": raw.metadata,
                "error": raw.error,
                "score": score,
                "missing_keywords": missing_keywords,
                "missing_sections": missing_sections,
                "duration_ms": duration_ms,
                "data_preview": data_text[:4000],
            })

        total_latency = int((time.time() - started) * 1000)
        aggregate = _mean(scores)
        return LayerResult(
            status="passed" if aggregate >= 0.80 and not failures else "failed",
            score=aggregate,
            scores={"tool_output_score": aggregate},
            failures=sorted(set(failures)),
            trace={"tool_results": tool_results},
            latency_ms=total_latency,
        )

    async def evaluate_agent(self, case: dict[str, Any]) -> LayerResult:
        expected_agent = case.get("expected_agent")
        if not expected_agent or expected_agent not in AGENT_CLASSES:
            return LayerResult(status="skipped", score=1.0, scores={}, trace={"reason": "no specialist agent expected"})

        started = time.time()
        errors: list[str] = []
        output_text = ""
        output_data: Any = None

        try:
            query_plan = await route_intent(case.get("expected_intent", "GENERAL_QUERY"), user_query=case["query"])
            agent = AGENT_CLASSES[expected_agent]()
            result_obj = await agent.analyze(query_plan, case["contract_id"], case["query"])
            output_data = result_obj.model_dump() if hasattr(result_obj, "model_dump") else result_obj
            output_text = _stringify(output_data)
        except Exception as exc:
            errors.append(str(exc))
            output_text = traceback.format_exc()

        latency_ms = int((time.time() - started) * 1000)
        keyword_score, found_keywords, missing_keywords = _coverage_score(case.get("expected_keywords", []), output_text)
        value_score, found_values, missing_values = _coverage_score(case.get("expected_values", {}), output_text)
        section_score, found_sections, missing_sections = _section_score(case.get("expected_sections", []), output_text)
        schema_score = 0.0 if errors else 1.0
        latency = _latency_score(latency_ms)
        scores = {
            "schema_score": schema_score,
            "keyword_score": keyword_score,
            "value_score": value_score,
            "section_score": section_score,
            "latency": latency,
        }
        aggregate = _mean(list(scores.values()))
        failures = []
        if errors:
            failures.append("agent_runtime_error")
        if section_score < 0.8:
            failures.append("agent_retrieval_miss")
        if keyword_score < 0.8:
            failures.append("agent_incomplete_answer")
        if value_score < 0.8:
            failures.append("agent_wrong_value")

        return LayerResult(
            status="passed" if aggregate >= 0.80 and not failures else "failed",
            score=aggregate,
            scores=scores,
            failures=sorted(set(failures)),
            trace={
                "agent": expected_agent,
                "output": output_data,
                "output_preview": output_text[:6000],
                "found_keywords": found_keywords,
                "missing_keywords": missing_keywords,
                "found_values": found_values,
                "missing_values": missing_values,
                "found_sections": found_sections,
                "missing_sections": missing_sections,
                "errors": errors,
            },
            error="\n".join(errors),
            latency_ms=latency_ms,
        )

    def _summarize(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        all_scores = [r["overall_score"] for r in results]
        by_category: dict[str, list[float]] = defaultdict(list)
        by_layer: dict[str, list[float]] = defaultdict(list)
        failure_counts: Counter[str] = Counter()

        for result in results:
            by_category[result.get("category", "uncategorized")].append(result["overall_score"])
            for layer_name, layer_result in result.get("layers", {}).items():
                by_layer[layer_name].append(layer_result.get("score", 0.0))
                for failure in layer_result.get("failures", []):
                    failure_counts[failure] += 1

        return {
            "mean_score": _mean(all_scores),
            "median_score": statistics.median(all_scores) if all_scores else 0.0,
            "pass_rate": sum(1 for score in all_scores if score >= 0.80) / len(all_scores) if all_scores else 0.0,
            "by_category": {
                category: {
                    "count": len(scores),
                    "mean_score": _mean(scores),
                }
                for category, scores in sorted(by_category.items())
            },
            "by_layer": {
                layer: {
                    "count": len(scores),
                    "mean_score": _mean(scores),
                }
                for layer, scores in sorted(by_layer.items())
            },
            "failure_counts": dict(failure_counts.most_common()),
        }


def load_cases(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text())
    return data.get("cases", data if isinstance(data, list) else [])


def parse_layers(
    raw_layers: str,
    include_ragas: bool = False,
    include_deepeval: bool = False,
) -> set[str]:
    if raw_layers.strip().lower() == "all":
        layers = {"chat", "tools", "agents", "deepeval"}
    else:
        layers = {part.strip().lower() for part in raw_layers.split(",") if part.strip()}
    if include_ragas:
        layers.add("ragas")
    if include_deepeval:
        layers.add("deepeval")
    valid = {"chat", "tools", "agents", "ragas", "deepeval"}
    unknown = layers - valid
    if unknown:
        raise ValueError(f"Unknown layer(s): {', '.join(sorted(unknown))}")
    return layers


def _deepeval_reference_text(case: dict[str, Any]) -> str:
    """Build a compact reference answer for DeepEval from golden-case fields."""
    parts = []
    if case.get("ragas_ground_truth"):
        parts.append(str(case["ragas_ground_truth"]))
    if case.get("expected_values"):
        values = case["expected_values"]
        if isinstance(values, dict):
            parts.append(
                "Expected values: "
                + "; ".join(f"{key}={value}" for key, value in values.items())
            )
        else:
            parts.append("Expected values: " + ", ".join(str(value) for value in values))
    if case.get("expected_keywords"):
        parts.append(
            "Expected facts or keywords: "
            + "; ".join(str(keyword) for keyword in case["expected_keywords"])
        )
    if case.get("expected_sections"):
        sections = [str(section).strip() for section in case["expected_sections"] if str(section).strip()]
        if sections:
            parts.append("Relevant sections:\n" + "\n\n".join(section[:1200] for section in sections[:3]))
    return "\n\n".join(part for part in parts if part.strip())


def run_deepeval(
    cases: list[dict[str, Any]],
    max_samples: int | None = None,
    evaluated_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    deepeval_cases = list(cases)
    if not deepeval_cases:
        return {"status": "skipped", "reason": "no cases"}

    try:
        from app.evaluation.deepeval_eval import DeepEvalEvaluator, DeepEvalSample
    except Exception as exc:
        return {"status": "skipped", "reason": f"deepeval import failed: {exc}"}

    results_by_id = {
        result.get("id"): result
        for result in (evaluated_results or [])
        if result.get("id")
    }

    grouped_samples: dict[str, list[Any]] = defaultdict(list)
    skipped_samples: list[dict[str, str]] = []
    for case in deepeval_cases:
        chat_trace = (
            results_by_id.get(case.get("id"), {})
            .get("layers", {})
            .get("chat", {})
            .get("trace", {})
        )
        answer = str(chat_trace.get("answer") or "").strip()
        contexts = _contexts_from_chat_trace(chat_trace)
        if answer and contexts:
            expected_output = _deepeval_reference_text(case)
            grouped_samples[case["contract_id"]].append(
                DeepEvalSample(
                    question=case["query"],
                    answer=answer,
                    contexts=contexts,
                    expected_output=expected_output,
                    metadata={
                        "case_id": case.get("id", ""),
                        "contract_id": case.get("contract_id", ""),
                        "category": case.get("category", ""),
                    },
                )
            )
        else:
            skipped_samples.append(
                {
                    "case_id": case.get("id", ""),
                    "reason": "missing actual chat answer or retrieved tool contexts",
                }
            )

    if not grouped_samples:
        return {
            "status": "skipped",
            "reason": "no usable agent-trace samples",
            "skipped_agent_samples": skipped_samples,
        }

    if max_samples:
        remaining = max_samples
        limited_samples: dict[str, list[Any]] = defaultdict(list)
        for contract_id, samples in grouped_samples.items():
            if remaining <= 0:
                break
            limited_samples[contract_id] = samples[:remaining]
            remaining -= len(limited_samples[contract_id])
        grouped_samples = limited_samples

    reports = {}
    for contract_id, samples in grouped_samples.items():
        try:
            evaluator = DeepEvalEvaluator()
            reports[contract_id] = evaluator.score(samples)
        except Exception as exc:
            reports[contract_id] = {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

    return {
        "status": "completed",
        "source": "agent_trace",
        "reports": reports,
        "skipped_agent_samples": skipped_samples,
    }


def run_ragas(
    cases: list[dict[str, Any]],
    max_samples: int | None = None,
    evaluated_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ragas_cases = [case for case in cases if case.get("ragas_ground_truth")]
    if max_samples:
        ragas_cases = ragas_cases[:max_samples]
    if not ragas_cases:
        return {"status": "skipped", "reason": "no cases with ragas_ground_truth"}

    try:
        from app.evaluation.ragas_eval import RagasEvaluator
    except Exception as exc:
        return {"status": "skipped", "reason": f"ragas import failed: {exc}"}

    results_by_id = {
        result.get("id"): result
        for result in (evaluated_results or [])
        if result.get("id")
    }

    grouped_agent_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped_agent_samples: list[dict[str, str]] = []
    for case in ragas_cases:
        chat_trace = (
            results_by_id.get(case.get("id"), {})
            .get("layers", {})
            .get("chat", {})
            .get("trace", {})
        )
        answer = str(chat_trace.get("answer") or "").strip()
        contexts = _contexts_from_chat_trace(chat_trace)
        if answer and contexts:
            grouped_agent_samples[case["contract_id"]].append(
                {
                    "question": case["query"],
                    "answer": answer,
                    "contexts": contexts,
                    "ground_truth": case["ragas_ground_truth"],
                    "case_id": case["id"],
                }
            )
        elif evaluated_results:
            skipped_agent_samples.append(
                {
                    "case_id": case.get("id", ""),
                    "reason": "missing actual chat answer or retrieved tool contexts",
                }
            )

    grouped_standalone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not grouped_agent_samples:
        for case in ragas_cases:
            grouped_standalone[case["contract_id"]].append(case)

    reports = {}
    source = "agent_trace" if grouped_agent_samples else "standalone_vector_prompt"

    for contract_id, samples in grouped_agent_samples.items():
        try:
            evaluator = RagasEvaluator()
            dataset = evaluator.build_dataset_from_samples(samples)
            if len(dataset) == 0:
                reports[contract_id] = {"status": "skipped", "reason": "no usable agent trace samples"}
            else:
                reports[contract_id] = evaluator.score(dataset)
                reports[contract_id]["sample_count"] = len(dataset)
        except Exception as exc:
            reports[contract_id] = {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

    for contract_id, group in grouped_standalone.items():
        test_set = [
            {
                "query": case["query"],
                "answer": case["ragas_ground_truth"],
            }
            for case in group
        ]
        try:
            evaluator = RagasEvaluator()
            dataset = asyncio.run(evaluator.build_eval_dataset(contract_id, test_set))
            reports[contract_id] = evaluator.score(dataset)
            reports[contract_id]["sample_count"] = len(dataset)
        except Exception as exc:
            reports[contract_id] = {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

    return {
        "status": "completed",
        "source": source,
        "reports": reports,
        "skipped_agent_samples": skipped_agent_samples,
    }


def collect_failures(results: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for case_result in results.get("results", []):
        if not case_result.get("failures"):
            continue
        failures.append({
            "id": case_result["id"],
            "category": case_result.get("category"),
            "query": case_result.get("query"),
            "overall_score": case_result.get("overall_score"),
            "failures": case_result.get("failures", []),
            "chat_trace": case_result.get("layers", {}).get("chat", {}).get("trace", {}),
        })
    return {
        "timestamp": results.get("timestamp"),
        "total_failures": len(failures),
        "failures": failures,
    }


def write_markdown_report(results: dict[str, Any], path: str) -> None:
    summary = results.get("summary", {})
    lines = [
        "# Full Contract-Agent Evaluation Report",
        "",
        f"Generated: {results.get('timestamp', '')}",
        f"Layers: {', '.join(results.get('layers', []))}",
        f"Total cases: {results.get('total_cases', 0)}",
        "",
        "## Executive Summary",
        "",
        f"- Mean score: {summary.get('mean_score', 0):.3f}",
        f"- Median score: {summary.get('median_score', 0):.3f}",
        f"- Pass rate: {summary.get('pass_rate', 0):.1%}",
        f"- Duration: {results.get('duration_ms', 0) / 1000:.1f}s",
        "",
        "## Category Scores",
        "",
        "| Category | Cases | Mean Score |",
        "|---|---:|---:|",
    ]
    for category, stats in summary.get("by_category", {}).items():
        lines.append(f"| {category} | {stats.get('count', 0)} | {stats.get('mean_score', 0):.3f} |")

    lines.extend([
        "",
        "## Layer Scores",
        "",
        "| Layer | Cases | Mean Score |",
        "|---|---:|---:|",
    ])
    for layer, stats in summary.get("by_layer", {}).items():
        lines.append(f"| {layer} | {stats.get('count', 0)} | {stats.get('mean_score', 0):.3f} |")

    lines.extend([
        "",
        "## Failure Types",
        "",
        "| Failure | Count |",
        "|---|---:|",
    ])
    failure_counts = summary.get("failure_counts", {})
    if failure_counts:
        for failure, count in failure_counts.items():
            lines.append(f"| `{failure}` | {count} |")
    else:
        lines.append("| None | 0 |")

    lines.extend([
        "",
        "## Case Results",
        "",
        "| Case | Category | Score | Failures |",
        "|---|---|---:|---|",
    ])
    for case in results.get("results", []):
        failures = ", ".join(f"`{failure}`" for failure in case.get("failures", [])) or "None"
        lines.append(
            f"| `{case.get('id')}` | {case.get('category', '')} | "
            f"{case.get('overall_score', 0):.3f} | {failures} |"
        )

    deepeval = results.get("deepeval")
    if deepeval:
        lines.extend([
            "",
            "## DeepEval",
            "",
            f"Status: `{deepeval.get('status')}`",
            f"Source: `{deepeval.get('source', 'unknown')}`",
            "",
        ])
        skipped = deepeval.get("skipped_agent_samples") or []
        if skipped:
            lines.append(f"- Skipped agent-trace samples: {len(skipped)}")
            lines.append("")
        reports = deepeval.get("reports", {})
        for contract_id, report in reports.items():
            lines.append(f"### {contract_id}")
            if report.get("status") == "failed":
                lines.append(f"- Error: `{report.get('error')}`")
                continue
            agg = report.get("aggregate_scores", {})
            if not agg:
                lines.append("- No aggregate scores returned.")
                continue
            for metric, score in agg.items():
                try:
                    lines.append(f"- {metric}: {float(score):.3f}")
                except Exception:
                    lines.append(f"- {metric}: {score}")

    ragas = results.get("ragas")
    if ragas:
        lines.extend([
            "",
            "## RAGAS",
            "",
            f"Status: `{ragas.get('status')}`",
            f"Source: `{ragas.get('source', 'unknown')}`",
            "",
        ])
        skipped = ragas.get("skipped_agent_samples") or []
        if skipped:
            lines.append(f"- Skipped agent-trace samples: {len(skipped)}")
            lines.append("")
        reports = ragas.get("reports", {})
        for contract_id, report in reports.items():
            lines.append(f"### {contract_id}")
            if report.get("status") == "failed":
                lines.append(f"- Error: `{report.get('error')}`")
                continue
            agg = report.get("aggregate_scores", {})
            if not agg:
                lines.append("- No aggregate scores returned.")
                continue
            for metric, score in agg.items():
                try:
                    lines.append(f"- {metric}: {float(score):.3f}")
                except Exception:
                    lines.append(f"- {metric}: {score}")

    lines.extend([
        "",
        "## Notes",
        "",
        "- UI, HTML chart rendering, SVG rendering, and browser visual checks are intentionally excluded.",
        "- `reports/evaluation/evaluation_results_full.json` contains complete traces and previews.",
        "- `reports/evaluation/evaluation_failures.json` contains the failure-focused diagnostic view.",
        "",
    ])

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines))


def write_json(path: str, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, default=_json_default) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run full backend evaluation for contract-agent.")
    parser.add_argument("--cases", default=DEFAULT_CASES, help="Path to golden cases JSON.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path for full JSON results.")
    parser.add_argument("--failures", default=DEFAULT_FAILURES, help="Path for failure-only JSON.")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Path for Markdown report.")
    parser.add_argument(
        "--layers",
        default="chat,tools,agents",
        help="Comma-separated layers: chat,tools,agents,deepeval,ragas or all.",
    )
    parser.add_argument("--include-ragas", action="store_true", help="Include RAGAS scoring.")
    parser.add_argument("--include-deepeval", action="store_true", help="Include DeepEval RAG scoring.")
    parser.add_argument("--ingest", action="store_true", help="Reingest and embed contracts before evaluating.")
    parser.add_argument("--seed-kpis", action="store_true", help="Extract and upsert KPI registry records before evaluating.")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip chunk-count validation. Use only when intentionally debugging empty retrieval.",
    )
    parser.add_argument("--chat-timeout", type=int, default=180, help="Per-case ChatAgent timeout in seconds.")
    parser.add_argument("--tool-timeout", type=int, default=60, help="Per-case tool-layer timeout in seconds.")
    parser.add_argument("--agent-timeout", type=int, default=180, help="Per-case specialist-agent timeout in seconds.")
    parser.add_argument("--max-cases", type=int, default=None, help="Limit number of cases.")
    parser.add_argument("--case-id", action="append", default=[], help="Run only a specific case id. Can repeat.")
    parser.add_argument("--ragas-max-samples", type=int, default=None, help="Limit RAGAS samples.")
    parser.add_argument("--deepeval-max-samples", type=int, default=None, help="Limit DeepEval samples.")
    parser.add_argument("--fail-under", type=float, default=None, help="Exit non-zero if mean score is below this threshold.")
    parser.add_argument(
        "--case-fail-under",
        type=float,
        default=None,
        help="Exit non-zero if any individual case overall score is below this threshold.",
    )
    parser.add_argument(
        "--layer-fail-under",
        type=float,
        default=None,
        help="Exit non-zero if any evaluated case layer score is below this threshold.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cases = load_cases(args.cases)
    layers = parse_layers(
        args.layers,
        include_ragas=args.include_ragas,
        include_deepeval=args.include_deepeval,
    )
    non_ragas_layers = layers - {"ragas", "deepeval"}

    evaluator = FullEvaluator(
        cases=cases,
        layers=non_ragas_layers,
        ingest=args.ingest,
        seed_kpis=args.seed_kpis,
        skip_preflight=args.skip_preflight,
        chat_timeout_s=args.chat_timeout,
        tool_timeout_s=args.tool_timeout,
        agent_timeout_s=args.agent_timeout,
        max_cases=args.max_cases,
        case_ids=set(args.case_id),
    )
    results = asyncio.run(evaluator.run())
    results["layers"] = sorted(layers)

    selected_cases = evaluator.cases
    if "deepeval" in layers:
        print("[full-eval] Running DeepEval")
        results["deepeval"] = run_deepeval(
            selected_cases,
            max_samples=args.deepeval_max_samples,
            evaluated_results=results.get("results", []),
        )

    if "ragas" in layers:
        print("[full-eval] Running RAGAS")
        results["ragas"] = run_ragas(
            selected_cases,
            max_samples=args.ragas_max_samples,
            evaluated_results=results.get("results", []),
        )

    failures = collect_failures(results)
    write_json(args.output, results)
    write_json(args.failures, failures)
    write_markdown_report(results, args.report)

    mean_score = results.get("summary", {}).get("mean_score", 0.0)
    print(f"[full-eval] Mean score: {mean_score:.3f}")
    print(f"[full-eval] Results: {Path(args.output).resolve()}")
    print(f"[full-eval] Failures: {Path(args.failures).resolve()}")
    print(f"[full-eval] Report: {Path(args.report).resolve()}")

    exit_code = 0
    if args.fail_under is not None and mean_score < args.fail_under:
        print(f"[full-eval] Mean score below threshold: {mean_score:.3f} < {args.fail_under:.3f}")
        exit_code = 1

    if args.case_fail_under is not None:
        failed_cases = [
            result for result in results.get("results", [])
            if result.get("overall_score", 0.0) < args.case_fail_under
        ]
        if failed_cases:
            print(
                "[full-eval] Case score threshold failed: "
                + ", ".join(f"{case['id']}={case.get('overall_score', 0):.3f}" for case in failed_cases[:10])
            )
            exit_code = 1

    if args.layer_fail_under is not None:
        failed_layers = []
        for result in results.get("results", []):
            for layer_name, layer_result in result.get("layers", {}).items():
                score = layer_result.get("score", 0.0)
                if score < args.layer_fail_under:
                    failed_layers.append(f"{result['id']}:{layer_name}={score:.3f}")
        if failed_layers:
            print("[full-eval] Layer score threshold failed: " + ", ".join(failed_layers[:10]))
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
