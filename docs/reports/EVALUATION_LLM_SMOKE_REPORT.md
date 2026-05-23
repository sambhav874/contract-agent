# Full Contract-Agent Evaluation Report

Generated: 2026-05-23T04:13:43.090811
Layers: chat, deepeval
Total cases: 4

## Executive Summary

- Mean score: 0.950
- Median score: 0.962
- Pass rate: 100.0%
- Duration: 62.2s

## Category Scores

| Category | Cases | Mean Score |
|---|---:|---:|
| compliance | 1 | 1.000 |
| general_query | 1 | 0.875 |
| key_dates | 1 | 0.962 |
| qa_answer | 1 | 0.962 |

## Layer Scores

| Layer | Cases | Mean Score |
|---|---:|---:|
| chat | 4 | 0.950 |

## Failure Types

| Failure | Count |
|---|---:|
| `intent_mismatch` | 3 |
| `incomplete_answer` | 1 |

## Case Results

| Case | Category | Score | Failures |
|---|---|---:|---|
| `case_0008_saas_agreement_parties` | general_query | 0.875 | `chat:incomplete_answer`, `chat:intent_mismatch` |
| `case_0009_saas_agreement_key_dates` | key_dates | 0.962 | `chat:intent_mismatch` |
| `case_0010_saas_agreement_compliance_1` | compliance | 1.000 | None |
| `case_0027_saas_agreement_qa_answer` | qa_answer | 0.962 | `chat:intent_mismatch` |

## DeepEval

Status: `completed`
Source: `agent_trace`

### saas_agreement
- answer_relevancy: 0.864
- contextual_precision: 0.738
- contextual_recall: 0.750
- contextual_relevancy: 0.408
- faithfulness: 0.979
- aggregate: 0.748

## Notes

- UI, HTML chart rendering, SVG rendering, and browser visual checks are intentionally excluded.
- `reports/evaluation/evaluation_results_full.json` contains complete traces and previews.
- `reports/evaluation/evaluation_failures.json` contains the failure-focused diagnostic view.
