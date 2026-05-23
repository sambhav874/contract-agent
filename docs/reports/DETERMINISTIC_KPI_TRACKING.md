# Deterministic Contract Performance Tracking: The Blueprint

This document outlines the architecture and execution of the "Zero-Hallucination" performance pipeline. It details how the system handles large-scale data (90+ records) and performs complex math (Summation/Averaging) to enforce contract penalties.

---

## 1. The Data Lifecycle (Step-by-Step)

When a delivery happens, it goes through three distinct "lives" in our system.

### Phase 1: Ingestion (The "Staging" Layer)
**Goal:** Capture the data immediately. No processing, no rules, just speed.
*   **Storage:** `raw_actuals` collection.
*   **JSON Example:**
    ```json
    {
      "source": "wms_log",
      "contract_id": "logistics_agreement_1.md",
      "data": { "qty": 4, "timestamp": "2026-05-12T12:00:00" },
      "status": "pending"
    }
    ```

### Phase 2: ETL Processing (The "Translation" Layer)
**Goal:** Map raw fields to Contract KPIs using your defined rules.
*   **Action:** The `ETLProcessor` reads the `pending` record, finds your mapping rule, and creates a **Normalized Record**.
*   **Storage:** `actuals` collection.
*   **JSON Example (Normalized):**
    ```json
    {
      "kpi_id": "kpi_600_test",
      "value": 4.0,
      "unit": "goods",
      "timestamp": "2026-05-12T12:00:00",
      "source": "etl:wms_log"
    }
    ```

### Phase 3: Aggregation (The "Judge" Layer)
**Goal:** Combine all normalized records and compare against the Contract.
*   **Action:** The `BreachEngine` looks at the KPI's `aggregation_type` (e.g., **SUM**).
*   **Math:** `SUM(record_1, record_2, ... record_90)`.
*   **Outcome:** If the total < 600, a **BREACH** object is generated with a calculated penalty.

---

## 2. Case Study: The 90-Day "Under-Delivery" Test

We tested a high-volume failure scenario to prove the system's accuracy.

### The Input
*   **Records:** 90 individual deliveries.
*   **Pattern:** 1 delivery per day, each containing exactly **4 units**.
*   **Total Expected:** 360 units.

### The Contract Requirement
*   **KPI:** "Total sum of received goods over 3 months must be 600."
*   **Target:** `600.0 units`.
*   **Threshold:** `OPERATOR_GTE` (>=).
*   **Penalty:** `$100,000.00`.

### The System Output (Actual CLI Report)
```text
│ KPI Name    │ Threshold  │ Actual      │ Status   │ Penalty    │
├─────────────┼────────────┼─────────────┼──────────┼────────────┤
│ Quarterly   │ >= 600.0   │ 360.0 units │  BREACH  │ $100,000.00│
│ Delivery    │ goods      │ (sum of 90) │          │            │
```

---

## 3. Why This Architecture is "Enterprise Grade"

1.  **Immutable History:** We never delete Phase 1 (Raw) data. If a supplier disputes a penalty, you can show them exactly which 90 days of logs led to the calculation.
2.  **Multi-KPI Fan-out:** Our engine allows one data point to update multiple targets (e.g., a "Volume" KPI and a "Quality" KPI simultaneously).
3.  **Dynamic Aggregation:** The system natively understands that "Volume" should be **SUMMED** while "Performance Scores" should be **AVERAGED**.
4.  **Zero Hallucination:** No AI is used in the math. It is 100% deterministic Python logic, ensuring financial auditability.

---

## 4. How to Use (For Developers)

To ingest data, simply send a POST request:
```bash
curl -X POST http://localhost:8000/contracts/{id}/raw-actuals \
-d '{"source": "your_system", "data": {"qty": 10}}'
```

To run the calculation:
```bash
curl -X POST http://localhost:8000/contracts/{id}/run-etl
```
