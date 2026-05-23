# Full Evaluation Dataset

`golden_cases.json` drives the backend evaluation harness in
`app.evaluation.full_evaluator`.

Each case can check:

- expected intent
- expected specialist agent
- expected tool calls
- expected sections/citations
- expected keywords and exact values
- tool-level retrieval checks
- optional DeepEval/RAGAS ground truth
- optional compound-query detection

Run the default backend evaluation:

```bash
python tests/evaluation/full_evaluation.py
```

Run everything, including DeepEval:

```bash
python tests/evaluation/full_evaluation.py --layers all
```

Run a strict 90+ quality gate across every case and layer:

```bash
python tests/evaluation/full_evaluation.py --layers all --fail-under 0.90 --case-fail-under 0.90 --layer-fail-under 0.90
```

Run DeepEval only after a small chat-layer sample:

```bash
python tests/evaluation/full_evaluation.py --layers chat,deepeval --deepeval-max-samples 3
```

Run a fast smoke test with short timeouts:

```bash
python tests/evaluation/full_evaluation.py --max-cases 1 --layers chat,tools --chat-timeout 45 --tool-timeout 30
```

For a fresh database, reingest contracts and seed the KPI registry first:

```bash
python tests/evaluation/full_evaluation.py --ingest --seed-kpis --include-deepeval
```

The evaluator runs a chunk-count preflight by default. If a selected contract has
zero stored chunks, the run stops before scoring because retrieval metrics would
be meaningless. Only bypass this with `--skip-preflight` when intentionally
debugging empty retrieval.

Generated UI, Chart.js rendering, SVG rendering, and browser visual checks are
intentionally out of scope for this evaluator.
