# Full Contract-Agent Evaluation Report

Generated: 2026-05-21T19:07:11.756723
Layers: agents, chat, ragas, tools
Total cases: 9

## Executive Summary

- Mean score: 0.677
- Median score: 0.650
- Pass rate: 22.2%
- Duration: 1817.9s

## Category Scores

| Category | Cases | Mean Score |
|---|---:|---:|
| clause_analysis | 1 | 0.649 |
| compliance | 1 | 0.667 |
| compound_orchestration | 1 | 0.667 |
| key_dates | 1 | 0.987 |
| kpi_extraction | 2 | 0.650 |
| obligation_tracking | 1 | 0.333 |
| risk_detection | 1 | 0.931 |
| summary | 1 | 0.555 |

## Layer Scores

| Layer | Cases | Mean Score |
|---|---:|---:|
| agents | 9 | 0.644 |
| chat | 9 | 0.385 |
| tools | 9 | 1.000 |

## Failure Types

| Failure | Count |
|---|---:|
| `timeout` | 4 |
| `wrong_value` | 1 |
| `agent_wrong_value` | 1 |
| `incomplete_answer` | 1 |
| `missing_citation` | 1 |
| `retrieval_miss` | 1 |
| `intent_mismatch` | 1 |

## Case Results

| Case | Category | Score | Failures |
|---|---|---:|---|
| `airport_kpi_on_time_delivery` | kpi_extraction | 0.650 | `chat:timeout` |
| `airport_kpi_meal_quality` | kpi_extraction | 0.650 | `chat:timeout` |
| `airport_obligation_reporting` | obligation_tracking | 0.333 | `agents:timeout`, `chat:timeout` |
| `airport_risk_termination` | risk_detection | 0.931 | `agents:agent_wrong_value`, `chat:wrong_value` |
| `airport_clause_section_701` | clause_analysis | 0.649 | `agents:timeout` |
| `airport_summary_contract` | summary | 0.555 | `agents:timeout`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `airport_key_dates` | key_dates | 0.987 | `chat:intent_mismatch` |
| `airport_compliance_penalties` | compliance | 0.667 | `chat:timeout` |
| `airport_compound_kpi_and_reporting` | compound_orchestration | 0.667 | `chat:timeout` |

## RAGAS

Status: `completed`

### airport_food_contract
- Error: `The resolution lifetime expired after 21.136 seconds: Server Do53:fe80::1%en0@53 answered [Errno 65] No route to host; Server Do53:192.168.1.1@53 answered The DNS operation timed out.; Server Do53:192.168.1.1@53 answered The DNS operation timed out.; Server Do53:192.168.1.1@53 answered The DNS operation timed out.; Server Do53:192.168.1.1@53 answered The DNS operation timed out.; Server Do53:192.168.1.1@53 answered The DNS operation timed out.; Server Do53:192.168.1.1@53 answered The DNS operation timed out.; Server Do53:192.168.1.1@53 answered The DNS operation timed out.`

## Notes

- UI, HTML chart rendering, SVG rendering, and browser visual checks are intentionally excluded.
- `evaluation_results_full.json` contains complete traces and previews.
- `evaluation_failures.json` contains the failure-focused diagnostic view.
