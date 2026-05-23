# Three Generated Contracts Evaluation Analysis

Generated: 2026-05-22

## Scope

This evaluation used the first three generated long-form contracts:

1. `full_eval_global_logistics`
2. `full_eval_healthcare_cloud`
3. `full_eval_solar_storage_epc`

The suite covered 15 total cases across summary, KPI extraction, obligation tracking, clause lookup, and risk analysis. UI, chart rendering, SVG rendering, and browser visual checks were intentionally excluded.

## Command Run

```bash
venv/bin/python -u tests/full_evaluation.py \
  --cases tests/eval/generated_three_contract_cases.json \
  --output evaluation_results_generated_three.json \
  --failures evaluation_failures_generated_three.json \
  --report EVALUATION_GENERATED_THREE_REPORT.md \
  --layers all \
  --ingest \
  --seed-kpis \
  --chat-timeout 180 \
  --tool-timeout 60 \
  --agent-timeout 180
```

## Headline Result

Overall result: not production-ready on this benchmark.

- Mean score: `0.563`
- Median score: `0.591`
- Pass rate: `20.0%` (`3/15` cases at or above `0.80`)
- Runtime: `26,430.3s`, about `7h 20m`
- Best layer: tools, mean `0.977`
- Weakest layer: ChatAgent orchestration, mean `0.268`
- Specialist agents mean: `0.444`

## Category Results

| Category | Cases | Mean Score | Assessment |
|---|---:|---:|---|
| Risk detection | 3 | 0.666 | Best functional area, but still misses exact values/citations |
| Summary | 3 | 0.640 | Partly useful, but summaries miss required sections/keywords |
| KPI extraction | 3 | 0.537 | Raw tools work, orchestration and long structured calls time out |
| Clause analysis | 3 | 0.529 | One strong case, two timeout-heavy failures |
| Obligation tracking | 3 | 0.442 | Weakest category; timeouts and incomplete specialist output |

## Layer Diagnosis

### Tool Layer

The tool layer is healthy. It scored `0.977` mean across all 15 cases.

This means ingestion, chunk storage, embeddings, search tools, summarize tool, and KPI registry lookup mostly work on the generated contracts. The failures are not primarily because the contracts cannot be parsed or retrieved.

Tool retrieval misses occurred in:

- `global_logistics_reporting_obligations`
- `solar_storage_risk_analysis`

### ChatAgent Layer

The ChatAgent layer is the main failure point. It scored `0.268` mean.

Major issues:

- Frequent timeouts on long cases.
- Missing section citations even when the answer is directionally correct.
- Incomplete answers for multi-part queries.
- Some wrong or missing exact values.
- One routing/delegation issue: `healthcare_cloud_clause_recovery_objectives` scored well overall but had `chat:wrong_agent`.
- `solar_storage_kpi_milestones_performance` was classified as `COMPLIANCE` instead of `KPI_QUERY`, likely because the query mentioned penalties and delay damages.

### Specialist Agent Layer

Specialist agents scored `0.444` mean.

Issues:

- Several direct agent evaluations timed out.
- Summary and risk agents often produced useful prose but missed expected sections or values.
- ObligationAgent struggled on larger cross-section obligation queries.
- RiskAgent was better than other specialists but still missed exact values such as caps, target percentages, and termination thresholds.

## Best Cases

| Case | Score | Notes |
|---|---:|---|
| `healthcare_cloud_clause_recovery_objectives` | 0.920 | Strong clause retrieval and value extraction for RTO/RPO |
| `global_logistics_risk_analysis` | 0.863 | Good risk answer, but missed EDI and termination-credit details |
| `healthcare_cloud_summary` | 0.817 | Passed by score, but still missed some expected coverage |

## Worst Cases

| Case | Score | Main Reason |
|---|---:|---|
| `global_logistics_clause_901` | 0.333 | Chat and specialist timeouts |
| `healthcare_cloud_kpi_availability_quality` | 0.333 | Chat and specialist timeouts |
| `solar_storage_summary` | 0.333 | Chat and specialist timeouts |
| `solar_storage_reporting_obligations` | 0.333 | Chat and specialist timeouts |
| `solar_storage_clause_step_in` | 0.333 | Chat and specialist timeouts |

## RAGAS Result

RAGAS completed, but the result is partially compromised.

The configured judge model repeatedly raised:

```text
Multiple candidates is not enabled for this model
```

That caused answer relevancy to be absent from aggregate scores and made the RAGAS phase very slow.

Available aggregate metrics:

| Contract | Context Precision | Context Recall | Faithfulness |
|---|---:|---:|---:|
| Global logistics | 0.067 | 0.633 | 1.000 |
| Healthcare cloud | 0.200 | 0.600 | 0.956 |
| Solar storage EPC | 0.200 | 0.467 | 0.980 |

Interpretation:

- Faithfulness is high: generated answers mostly stay grounded in retrieved text.
- Context precision is low: retrieval often includes broad or generic context alongside the exact clauses.
- Context recall is moderate: relevant information is often present, but not consistently complete.
- RAGAS judge configuration needs repair before treating RAGAS as a reliable acceptance gate.

## Main Findings

1. The backend retrieval/tooling foundation is strong.
2. The full ChatAgent orchestration path is too slow and timeout-prone for long contracts.
3. The agents need stricter citation and exact-value discipline.
4. Broad multi-part questions need decomposition with bounded sub-queries and bounded output size.
5. RAGAS should not run in the default full suite until the judge model and timeout behavior are fixed.

## Recommended Next Fixes

1. Run normal regression evaluation without RAGAS by default:

```bash
venv/bin/python -u tests/full_evaluation.py \
  --cases tests/eval/generated_three_contract_cases.json \
  --output evaluation_results_generated_three_no_ragas.json \
  --failures evaluation_failures_generated_three_no_ragas.json \
  --report EVALUATION_GENERATED_THREE_NO_RAGAS_REPORT.md \
  --layers chat,tools,agents \
  --ingest \
  --seed-kpis
```

2. Fix RAGAS separately:

- Use a judge model that supports multiple candidates, or disable the answer relevancy metric.
- Add per-metric timeout limits that fail fast.
- Write partial main-suite results before entering RAGAS.

3. Fix ChatAgent timeouts:

- Add hard request-level timeouts in Gemini calls.
- Reduce multi-step planning for simple clause, KPI, and obligation queries.
- Stream and finalize partial answers rather than waiting indefinitely.
- Cap retrieval context and output length per specialist.

4. Improve scoring quality:

- Require every specialist answer to include section labels.
- Add exact-value post-checks for expected numbers, percentages, money amounts, and dates.
- For KPI queries, prefer structured extraction directly from retrieved KPI sections before prose synthesis.

5. Improve retrieval precision:

- Boost exact section-title matches.
- Add section-aware filters for queries like `Section 9.01` and `Section 11.02`.
- Improve ranking for dense obligation/risk queries so the exact clause appears in top results.

## Files Produced

- `tests/eval/generated_three_contract_cases.json`
- `evaluation_results_generated_three.json`
- `evaluation_failures_generated_three.json`
- `EVALUATION_GENERATED_THREE_REPORT.md`
- `EVALUATION_GENERATED_THREE_ANALYSIS.md`
