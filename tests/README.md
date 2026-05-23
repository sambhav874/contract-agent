# Test Layout

- `unit/`: fast, mocked tests for agents, ingestion, retrieval, tools, tasks, and utilities.
- `integration/`: API-level tests using FastAPI test clients and mocked backing services.
- `evaluation/`: backend evaluation runner and golden case definitions.
- `fixtures/contracts/`: shared contract fixtures used by the pytest suite.
- `fixtures/full_eval_contracts/`: generated long-form contracts used by backend evaluation.
