# Contract Intelligence Agent Evaluation Report

## Executive Summary

**Source output:** `evaluation_results.json`
**Contract tested:** Airport Food Contract (`tests/fixtures/airport_food.md`)
**Contract ID:** `airport_food_contract`
**Run timestamp:** 2026-05-21 17:20:38
**Sections detected:** 46
**Chunks created:** 105
**Total queries:** 14

The latest evaluation shows a materially healthier ingestion and retrieval setup than the older report: the contract produced 105 chunks from 46 detected sections, and the run completed with a 0% error rate. Overall answer quality is acceptable but uneven.

The agent performs best on risk detection and clause analysis. The weakest area is KPI extraction, mainly because two KPI questions failed at the tool/retrieval orchestration layer rather than simply returning incomplete answers. Obligation tracking is also mixed: two obligation questions passed, but the reporting-obligations query produced a confident false negative despite Article VI containing explicit daily, monthly, and quarterly reporting requirements.

## Overall Results

| Metric | Result | Interpretation |
|---|---:|---|
| Total queries | 14 | Four evaluation categories |
| Average quality | 0.735 | Moderate overall performance |
| Average relevance | 0.776 | Usually finds related material |
| Average completeness | 0.695 | Misses specific expected values too often |
| Error rate | 0.0% | No top-level query execution failures |
| Average latency | 63.5s | Slow for interactive use |

## Test Distribution

| Category | Query Count | Share | Intent |
|---|---:|---:|---|
| KPI extraction | 5 | 35.7% | `kpi` |
| Risk detection | 3 | 21.4% | `risk` |
| Obligation tracking | 3 | 21.4% | `obligations` |
| Clause analysis | 3 | 21.4% | `clause` |

The test set is intentionally KPI-heavy. This makes sense for this contract because Article IV contains a large KPI framework, but it means aggregate quality is heavily influenced by KPI extraction failures.

## Category Performance

| Category | Queries | Avg Quality | Avg Relevance | Avg Completeness | Avg Latency |
|---|---:|---:|---:|---:|---:|
| Risk detection | 3 | 0.97 | 1.00 | 0.93 | 31.2s |
| Clause analysis | 3 | 0.93 | 0.95 | 0.91 | 38.6s |
| Obligation tracking | 3 | 0.67 | 0.67 | 0.67 | 109.2s |
| KPI extraction | 5 | 0.52 | 0.60 | 0.44 | 70.5s |

### Key Takeaways

Risk detection is the strongest capability in this run. Food safety penalties and liability exposure both scored perfectly, and termination risk scored 0.90 with only the cure-period value missing.

Clause analysis is also strong. The contract term and sustainability queries were mostly correct, with small misses caused partly by exact-string matching.

KPI extraction is unreliable. Three KPI queries were good or perfect, but two core KPI questions returned no usable contract data because the response reported internal retrieval/classification failures.

Obligation tracking has a serious factuality issue. The reporting-obligations answer stated that no reporting obligations exist, even though Article VI expressly lists daily reports, monthly reports, quarterly business reviews, and audit rights.

## Query-Level Results

| Category | Query | Quality | Status | Notes |
|---|---|---:|---|---|
| KPI extraction | What are the on-time delivery targets and penalties? | 0.00 | Fail | Response reported a `classify_intent()` argument error and retrieved no data. Expected Section 4.02 values were all missed. |
| KPI extraction | What are the volume discount tiers? | 0.80 | Partial pass | All volume thresholds were found. The compact expected range `2.5%-8.0%` was not matched, although the answer listed the tiers. |
| KPI extraction | What is the meal quality score target and penalty structure? | 0.00 | Fail | Response reported retrieval/sub-agent errors and missed all Section 4.05 target and penalty values. |
| KPI extraction | List all pricing for Business Class meals | 0.80 | Partial pass | Correctly found `$28.50`, `$42.00`, and `3.5%`; missed the exact compact range `$28.50-$42.00`. |
| KPI extraction | What are the waste rate targets and penalties? | 1.00 | Pass | Found expected waste target, bonus threshold, and penalty values. |
| Risk detection | What are the termination risks for the Concessionaire? | 0.90 | Strong pass | Found termination, food safety, hospitalization, and `$500,000`; missed `30 days`. |
| Risk detection | Identify food safety incident penalties | 1.00 | Pass | Found the expected food safety penalty ladder. |
| Risk detection | What are the liability caps or unlimited exposures? | 1.00 | Pass | Found liability, cap, and unlimited exposure concepts. |
| Obligation tracking | What are the reporting obligations? | 0.00 | Fail | Incorrectly answered that no reporting obligations exist. Expected Article VI reporting deadlines were all missed. |
| Obligation tracking | What are the special meal availability requirements? | 1.00 | Pass | Found special-meal notice periods and availability target. |
| Obligation tracking | What are the equipment uptime requirements? | 1.00 | Pass | Found equipment uptime target and relevant equipment terms. |
| Clause analysis | What is the contract term and renewal structure? | 0.88 | Strong pass | Found 2027, 2031, and January 1. Missed expected string `5 years` because the response used `five-year`. |
| Clause analysis | What are the key definitions related to meal delivery? | 1.00 | Pass | Found expected defined terms. |
| Clause analysis | What sustainability requirements exist? | 0.92 | Strong pass | Found packaging, 25%, 50%, and 60%; missed exact phrase `locally sourced`. |

## Critical Failures

### 1. On-Time Delivery KPI Retrieval Failure

The answer did not fail because the contract lacks the data. Section 4.02 contains the required target and penalty structure:

- Target: at least 98.5% on-time delivery
- Tier 1: 95.0% to 96.9%, $2,500 per percentage point below 97%
- Tier 2: below 95.0%, $5,000 per percentage point below 97% plus a corrective action plan

The response instead reported an internal `classify_intent()` call failure involving an unsupported `prior_history` argument. This points to a tool or agent-interface mismatch.

### 2. Meal Quality KPI Retrieval Failure

Section 4.05 contains the expected values:

- Target: at least 4.5/5.0 average score
- 4.0 to 4.49: $5,000 monthly penalty
- 3.5 to 3.99: $15,000 monthly penalty
- 3.0 to 3.49: $30,000 plus CAP
- Below 3.0: $50,000 plus contract review

The answer again reported retrieval/sub-agent errors and provided no specific values. This appears related to the same orchestration issue as the on-time delivery failure.

### 3. Reporting Obligations False Negative

The reporting-obligations answer is the most concerning factual failure. It confidently stated that there are no reporting obligations, but Article VI includes:

- Daily reports by 10:00 AM for previous-day operations
- Monthly reports due by the 10th of the following month
- Quarterly business review meetings
- Audit rights and records retention obligations

This is not just an exact-match scoring problem. It is a substantive answer-quality issue.

## Partial Misses and Scoring Artifacts

Several non-perfect scores are partly caused by brittle exact-string evaluation:

- Volume discounts: the answer lists each tier, but the evaluator expects the compact value `2.5%-8.0%`.
- Business Class pricing: the answer gives `$28.50` and `$42.00`, but the evaluator expects `$28.50-$42.00`.
- Contract term: the answer says `fixed five-year term`, while the evaluator expects `5 years`.
- Sustainability: the answer appears to capture local sourcing conceptually, but misses the exact phrase `locally sourced`.

These should not be treated the same as the hard failures. The evaluator should normalize punctuation, numeric words, ranges, spacing, and common phrase variants before marking expected values as missing.

## Latency Analysis

| Query | Latency |
|---|---:|
| What are the volume discount tiers? | 273.8s |
| What are the reporting obligations? | 269.9s |
| What sustainability requirements exist? | 49.0s |
| List all pricing for Business Class meals | 47.0s |
| What are the liability caps or unlimited exposures? | 42.8s |

The average latency is 63.5 seconds, but the median is closer to 37.8 seconds. Two outliers, volume discounts and reporting obligations, dominate the average. Both should be inspected for repeated retrieval loops, slow LLM calls, or planner retries.

## Recommendations

### Priority 1: Fix the `classify_intent()` Interface Mismatch

The two zero-score KPI failures mention an unsupported `prior_history` argument. Find the caller passing `prior_history` and either update `classify_intent()` to accept it or remove the argument at the call site. This should be treated as a blocking bug because it prevents the agent from retrieving obvious KPI data.

### Priority 2: Investigate Reporting-Obligations Retrieval

The reporting query should retrieve Article VI. Add a focused regression test for:

```text
What are the reporting obligations?
```

Expected answer should include daily 10:00 AM reports, monthly reports due by the 10th, quarterly review meetings, and audit/records obligations.

### Priority 3: Improve Value Matching in the Evaluator

Normalize expected and actual values before scoring:

- Treat `five-year`, `five year`, and `5 years` as equivalent.
- Treat `$28.50 - $42.00`, `$28.50-$42.00`, and `$28.50 and $42.00` as equivalent range evidence.
- Treat tier lists containing 2.5%, 4.0%, 6.0%, and 8.0% as satisfying the discount range.
- Normalize punctuation, whitespace, en dashes, and percentage spacing.

### Priority 4: Add Per-Query Debug Metadata

The report currently depends on the final answer text. Future evaluation output should include:

- Routed intent
- Retrieval queries issued
- Retrieved chunk IDs and section paths
- Tool errors and stack traces
- Number of retrieval rounds
- Whether the answer came from direct retrieval, synthesized sub-agents, or fallback response

This would make failures much faster to diagnose.

### Priority 5: Reduce Slow Query Paths

Set soft timeouts or max retrieval rounds for evaluation runs. For outliers above 120 seconds, capture which step consumed the time. The current suite has two near-270-second queries, which makes iteration slow and noisy.

## Overall Assessment

The agent is no longer blocked by the ingestion/chunking problem described in the older report. Chunking is now adequate for this fixture, and several categories are performing well.

The remaining problems are more targeted:

1. A tool/interface bug breaks at least two KPI queries.
2. Reporting-obligation retrieval or synthesis can produce a confident false negative.
3. The evaluator is too strict for semantically correct numeric/range answers.
4. Latency outliers make the suite expensive to run repeatedly.

Fixing the `classify_intent()` mismatch and adding a regression test for Article VI reporting should produce the largest immediate score improvement.
