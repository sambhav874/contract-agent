# Project Report: Rule-Based Deterministic ETL Pipeline

## 1. Objective
To implement a robust, high-performance ingestion and transformation pipeline for contract performance data ("Actuals"). The system must function deterministically without LLM reliance for extraction, supporting heterogeneous data sources (IoT, ERP, Logistics) and dynamic mathematical aggregations.

## 2. Core Architecture

### A. The Staging Layer (`RawActual`)
*   **Purpose**: Acts as a buffer for raw data.
*   **How it works**: Data is ingested via `POST /contracts/{id}/raw-actuals`. It supports any JSON schema and "parks" the data in a `pending` state.
*   **Benefit**: Decouples ingestion from processing, ensuring high availability and auditability.

### B. The Mapping Layer (`MappingRule`)
*   **Purpose**: Defines the "Translation Manual" for each contract.
*   **Configuration**: Users define rules that match a `source` prefix and specify which JSON field (using dot-notation) maps to which `kpi_id`.
*   **Example**: `source_match: "wms_log"` -> `field: "qty"` -> `kpi_id: "VOL_001"`.

### C. The Processing Layer (`ETLProcessor`)
*   **Purpose**: Executes the transformation logic.
*   **Action**: Iterates through `pending` raw records, resolves field paths, and creates normalized `OperationalActual` entries.
*   **Safety**: If no mapping rule is found, the record is `skipped` rather than guessed, preventing data pollution.

### D. The Dynamic Breach Engine
*   **Purpose**: Evaluates performance against contract thresholds.
*   **Dynamic Aggregation**: Now supports multiple math modes:
    *   **SUM**: Adds values (e.g., Total Monthly Delivery Volume).
    *   **AVG**: Calculates the mean (e.g., Average Quality Score).
    *   **MIN/MAX**: Identifies extremes (e.g., Temperature spikes).
    *   **LATEST**: Captures current state (e.g., Inventory level).

---

## 3. End-to-End Verification (The "300 Goods" Test)

### Setup:
1.  **Contract**: `logistics_agreement_1.md` was created with a KPI requiring **300 units/month**.
2.  **KPI Configuration**: The extracted KPI was manually tuned to `aggregation_type: "sum"`.
3.  **Mapping**: A rule was created for the `wms_log` source.

### Execution:
1.  **Ingestion**: Sent three separate JSON batches (100, 100, and 50 units).
2.  **ETL Run**: The processor correctly resolved all 3 batches.
3.  **Breach Check**:
    *   **Calculation**: `100 + 100 + 50 = 250`.
    *   **Comparison**: `250 < 300` (Threshold).
    *   **Result**: 🔴 **BREACH** detected.
    *   **Penalty**: **50,000 INR** automatically calculated and logged.

---

## 4. Conclusion
The system successfully transitioned from a fuzzy, LLM-based inference model to a precise, **Rule-Based Engine**. This provides the reliability required for financial penalty calculations while maintaining the flexibility to handle any data schema through its decoupled staging and mapping architecture.
