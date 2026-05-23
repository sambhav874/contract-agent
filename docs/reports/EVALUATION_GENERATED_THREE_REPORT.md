# Full Contract-Agent Evaluation Report

Generated: 2026-05-22T11:12:26.091237
Layers: agents, chat, ragas, tools
Total cases: 15

## Executive Summary

- Mean score: 0.563
- Median score: 0.591
- Pass rate: 20.0%
- Duration: 26430.3s

## Category Scores

| Category | Cases | Mean Score |
|---|---:|---:|
| clause_analysis | 3 | 0.529 |
| kpi_extraction | 3 | 0.537 |
| obligation_tracking | 3 | 0.442 |
| risk_detection | 3 | 0.666 |
| summary | 3 | 0.640 |

## Layer Scores

| Layer | Cases | Mean Score |
|---|---:|---:|
| agents | 15 | 0.444 |
| chat | 15 | 0.268 |
| tools | 15 | 0.977 |

## Failure Types

| Failure | Count |
|---|---:|
| `timeout` | 7 |
| `incomplete_answer` | 4 |
| `missing_citation` | 4 |
| `retrieval_miss` | 4 |
| `agent_incomplete_answer` | 3 |
| `agent_retrieval_miss` | 3 |
| `search_contract_clauses:tool_retrieval_miss` | 2 |
| `wrong_value` | 2 |
| `agent_wrong_value` | 2 |
| `false_negative` | 1 |
| `wrong_agent` | 1 |

## Case Results

| Case | Category | Score | Failures |
|---|---|---:|---|
| `global_logistics_summary` | summary | 0.771 | `agents:agent_incomplete_answer`, `agents:agent_retrieval_miss`, `chat:false_negative`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `global_logistics_kpi_pickup_delivery` | kpi_extraction | 0.634 | `chat:timeout` |
| `global_logistics_reporting_obligations` | obligation_tracking | 0.591 | `chat:timeout`, `tools:search_contract_clauses:tool_retrieval_miss` |
| `global_logistics_clause_901` | clause_analysis | 0.333 | `agents:timeout`, `chat:timeout` |
| `global_logistics_risk_analysis` | risk_detection | 0.863 | `agents:agent_wrong_value`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss`, `chat:wrong_value` |
| `healthcare_cloud_summary` | summary | 0.817 | `agents:agent_incomplete_answer`, `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `healthcare_cloud_kpi_availability_quality` | kpi_extraction | 0.333 | `agents:timeout`, `chat:timeout` |
| `healthcare_cloud_privacy_security_obligations` | obligation_tracking | 0.403 | `agents:agent_incomplete_answer`, `agents:agent_retrieval_miss`, `agents:agent_wrong_value`, `chat:timeout` |
| `healthcare_cloud_clause_recovery_objectives` | clause_analysis | 0.920 | `chat:wrong_agent` |
| `healthcare_cloud_risk_termination` | risk_detection | 0.479 | `agents:timeout`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss`, `chat:wrong_value` |
| `solar_storage_summary` | summary | 0.333 | `agents:timeout`, `chat:timeout` |
| `solar_storage_kpi_milestones_performance` | kpi_extraction | 0.644 | `chat:timeout` |
| `solar_storage_reporting_obligations` | obligation_tracking | 0.333 | `agents:timeout`, `chat:timeout` |
| `solar_storage_clause_step_in` | clause_analysis | 0.333 | `agents:timeout`, `chat:timeout` |
| `solar_storage_risk_analysis` | risk_detection | 0.657 | `agents:agent_incomplete_answer`, `agents:agent_retrieval_miss`, `agents:agent_wrong_value`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss`, `chat:wrong_value`, `tools:search_contract_clauses:tool_retrieval_miss` |

## RAGAS

Status: `completed`

### full_eval_global_logistics
- context_precision: 0.067
- context_recall: 0.633
- faithfulness: 1.000
### full_eval_healthcare_cloud
- context_precision: 0.200
- context_recall: 0.600
- faithfulness: 0.956
### full_eval_solar_storage_epc
- context_precision: 0.200
- context_recall: 0.467
- faithfulness: 0.980

## Notes

- UI, HTML chart rendering, SVG rendering, and browser visual checks are intentionally excluded.
- `evaluation_results_full.json` contains complete traces and previews.
- `evaluation_failures.json` contains the failure-focused diagnostic view.
