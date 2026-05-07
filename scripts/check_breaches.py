"""Breach engine: evaluate KPIs against actuals and persist results to MongoDB."""

import json
import asyncio
import os
import sys
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.mongodb import MongoDB
from app.db.models import BreachResult


class BreachEngine:
    """Compare operational actuals against KPI thresholds and persist results."""

    @staticmethod
    def calculate_actual(data: List[Dict], kpi_name: str) -> float:
        if not data:
            return 0.0
        if isinstance(data, (int, float)):
            return float(data)

        # Percentage-based KPIs (delivery, fulfillment, compliance, uptime)
        if any(k in kpi_name for k in ["KPI-1", "KPI-3", "KPI-6", "KPI-13", "Delivery", "Fulfillment", "Compliance", "Uptime"]):
            if "is_on_time" in data[0]:
                s = sum(1 for d in data if d.get("is_on_time") in (True, "true", "True"))
                return (s / len(data)) * 100
            if "is_fulfilled" in data[0]:
                s = sum(1 for d in data if d.get("is_fulfilled") in (True, "true", "True"))
                return (s / len(data)) * 100
            if "is_within_temp" in data[0]:
                s = sum(1 for d in data if d.get("is_within_temp") in (True, "true", "True"))
                return (s / len(data)) * 100
            if "is_operational" in data[0]:
                s = sum(1 for d in data if d.get("is_operational") in (True, "true", "True"))
                return (s / len(data)) * 100

        # Quality scores
        if "KPI-4" in kpi_name or "Quality" in kpi_name:
            scores = [float(d.get("score", 0)) for d in data if d.get("score") is not None]
            return sum(scores) / len(scores) if scores else 0.0

        # Complaint rates (per 10,000 meals)
        if "KPI-10" in kpi_name or "Complaint" in kpi_name:
            complaints = sum(float(d.get("complaints", 0)) for d in data)
            meals = sum(float(d.get("meals_served", 10000)) for d in data)
            return (complaints / meals) * 10000 if meals > 0 else 0.0

        # Waste rate (%)
        if "KPI-9" in kpi_name or "Waste" in kpi_name:
            waste = sum(float(d.get("waste", 0)) for d in data)
            prepared = sum(float(d.get("prepared", 1)) for d in data)
            return (waste / prepared) * 100 if prepared > 0 else 0.0

        # Incident counts
        if any(k in kpi_name for k in ["KPI-5", "KPI-7", "Allergen", "Safety", "Hospitalization"]):
            return sum(float(d.get("incidents", d.get("value", 0))) for d in data)

        # Delay minutes
        if "KPI-2" in kpi_name or "Delay" in kpi_name:
            return max(float(d.get("delay_minutes", d.get("value", 0))) for d in data)

        # Financial / pricing — average the 'value' field
        if any(k in kpi_name for k in ["FIN-", "Rate", "Pricing", "Discount"]):
            values = [float(d.get("value", 0)) for d in data if d.get("value") is not None]
            return sum(values) / len(values) if values else 0.0

        # Default: average values
        values = [float(d.get("value", 0)) for d in data if d.get("value") is not None]
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def evaluate_breach(actual: float, operator: str, v_min: Optional[float], v_max: Optional[float]) -> bool:
        if operator == "<=" and v_min is None and v_max is not None:
            v_min = v_max
        if v_min is None and operator != "between":
            return False
        if operator == ">=": return actual < v_min
        if operator == "<=": return actual > v_min
        if operator == "==": return abs(actual - v_min) > 0.001
        if operator == ">":  return actual <= v_min
        if operator == "<":  return actual >= v_min
        if operator == "between":
            if v_min is None or v_max is None: return False
            return not (v_min <= actual <= v_max)
        return False

    @staticmethod
    def classify_severity(is_breach: bool, penalty_amount: float, actual: float, threshold: float) -> str:
        if not is_breach:
            return "LOW"
        ratio = abs(actual - threshold) / max(abs(threshold), 1)
        if penalty_amount >= 10000 or ratio > 0.5:
            return "CRITICAL"
        if penalty_amount >= 2000 or ratio > 0.2:
            return "HIGH"
        return "MEDIUM"

    async def get_actuals_from_db(self, contract_id: str, kpi_id: str, kpi_name: str) -> List[Dict]:
        # Use "actuals" collection (standardized name)
        collection = MongoDB.get_collection("actuals")
        match = re.search(r"(KPI-\d+)", kpi_name)
        base_code = match.group(1) if match else kpi_id

        cursor = collection.find({
            "contract_id": contract_id,
            "$or": [
                {"kpi_id": kpi_id},
                {"kpi_id": base_code},
                {"kpi_id": {"$regex": f"^{base_code}", "$options": "i"}}
            ]
        })
        return await cursor.to_list(length=1000)


async def get_extracted_kpis(contract_id: str) -> List[Dict[str, Any]]:
    """Get KPIs from the kpis collection (primary) or fall back to analysis jobs."""
    kpis_coll = MongoDB.get_collection("kpis")
    kpis = await kpis_coll.find({"contract_id": contract_id}).to_list(None)
    if kpis:
        for k in kpis:
            if "_id" in k:
                k["_id"] = str(k["_id"])
        return kpis

    # Fallback: get from analysis job result
    job = await MongoDB.get_latest_job(contract_id, "kpi")
    if not job:
        return []
    return job.get("result", {}).get("structured", {}).get("kpis", [])


async def seed_actuals_to_db(contract_id: str, actuals_dir: str):
    """Seed local actuals files into the 'actuals' MongoDB collection."""
    collection = MongoDB.get_collection("actuals")
    if not os.path.exists(actuals_dir):
        print(f"  [SKIP] Directory {actuals_dir} not found.")
        return 0

    count = 0
    for filename in os.listdir(actuals_dir):
        kpi_id = filename.split(".")[0]
        file_path = os.path.join(actuals_dir, filename)
        data = []

        if filename.endswith(".json"):
            with open(file_path, "r") as f:
                data = json.load(f)
        elif filename.endswith(".csv"):
            import csv
            with open(file_path, "r") as f:
                data = list(csv.DictReader(f))

        if data:
            await collection.delete_many({"contract_id": contract_id, "kpi_id": kpi_id})
            for entry in data:
                entry["contract_id"] = contract_id
                entry["kpi_id"] = kpi_id
                entry["source"] = "manual_seed"
                entry["timestamp"] = entry.get("timestamp", datetime.now().isoformat())
            await collection.insert_many(data)
            count += len(data)

    return count


async def run_evaluation(contract_id: str, actuals_dir: str = "data/actuals") -> List[Dict]:
    """Full evaluation pipeline: seed actuals → evaluate breaches → persist results."""
    engine = BreachEngine()

    # 1. Seed actuals from files if directory exists
    if os.path.exists(actuals_dir):
        print(f"  Seeding actuals from {actuals_dir}...")
        n = await seed_actuals_to_db(contract_id, actuals_dir)
        print(f"  Seeded {n} records.")

    # 2. Get extracted KPIs
    kpis = await get_extracted_kpis(contract_id)
    if not kpis:
        print(f"  No KPIs found for {contract_id}.")
        return []

    # 3. Clear old breach results for this contract
    breaches_coll = MongoDB.get_collection("breaches")
    await breaches_coll.delete_many({"contract_id": contract_id})

    # 4. Evaluate each KPI
    results = []
    for kpi in kpis:
        kpi_id = kpi["kpi_id"]
        kpi_name = kpi.get("name", kpi_id)

        data = await engine.get_actuals_from_db(contract_id, kpi_id, kpi_name)
        if not data:
            continue

        actual_val = engine.calculate_actual(data, kpi_name)
        op = kpi.get("operator", ">=")
        v_min = kpi.get("value_min")
        v_max = kpi.get("value_max")

        is_breach = engine.evaluate_breach(actual_val, op, v_min, v_max)

        penalty_amount = 0.0
        penalty_triggered = None
        if is_breach and kpi.get("consequence_value"):
            penalty_amount = float(kpi["consequence_value"])
            penalty_triggered = kpi.get("trigger_condition")

        severity = engine.classify_severity(is_breach, penalty_amount, actual_val, v_min or 0)

        breach = BreachResult(
            contract_id=contract_id,
            kpi_id=kpi_id,
            actual_value=actual_val,
            threshold_value=v_min or v_max or 0,
            operator=op,
            is_breach=is_breach,
            penalty_triggered=penalty_triggered,
            penalty_amount=penalty_amount,
            remediation=kpi.get("remediation"),
            remediation_sla=kpi.get("remediation_sla"),
        )

        doc = breach.model_dump()
        doc["severity"] = severity
        doc["kpi_name"] = kpi_name

        # 5. Persist to MongoDB
        await breaches_coll.insert_one(doc)
        results.append(doc)

        status = f"[{severity}]" if is_breach else "[OK]"
        print(f"  {status} {kpi_name}: actual={actual_val:.2f}, threshold={op} {v_min}")

    print(f"\n  Total: {len(results)} flags ({sum(1 for r in results if r['is_breach'])} breaches)")
    return results


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run breach evaluation")
    parser.add_argument("--contract-id", default="FINAL-TEST-001", help="Contract ID to evaluate")
    parser.add_argument("--actuals-dir", default="data/actuals", help="Directory with actuals files")
    args = parser.parse_args()

    await MongoDB.connect()
    print(f"\n{'='*60}")
    print(f"  BREACH EVALUATION — {args.contract_id}")
    print(f"{'='*60}\n")

    results = await run_evaluation(args.contract_id, args.actuals_dir)

    await MongoDB.disconnect()
    return results


if __name__ == "__main__":
    asyncio.run(main())
