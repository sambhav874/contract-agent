import json
import asyncio
import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.mongodb import MongoDB
from app.config import settings

class BreachEngine:
    @staticmethod
    def calculate_actual(data: List[Dict], kpi_name: str) -> float:
        """
        Calculates the actual value from a list of data points.
        If data is already a single value (from DB aggregation), returns it.
        """
        if not data:
            return 0.0
            
        if isinstance(data, (int, float)):
            return float(data)

        # Logic for Percentage Rates
        if any(k in kpi_name for k in ["KPI-1", "KPI-3", "KPI-5", "KPI-6", "KPI-13", "Delivery", "Fulfillment", "Compliance", "Uptime"]):
            if "is_on_time" in data[0]:
                successes = sum(1 for d in data if d.get("is_on_time") is True or str(d.get("is_on_time")).lower() == "true")
                return (successes / len(data)) * 100
            if "is_fulfilled" in data[0]:
                successes = sum(1 for d in data if d.get("is_fulfilled") is True or str(d.get("is_fulfilled")).lower() == "true")
                return (successes / len(data)) * 100
            if "is_within_temp" in data[0]:
                successes = sum(1 for d in data if d.get("is_within_temp") is True or str(d.get("is_within_temp")).lower() == "true")
                return (successes / len(data)) * 100
                
        # Logic for Averages/Rates (Quality Scores, Complaints)
        if "KPI-4" in kpi_name or "Quality" in kpi_name:
            scores = [d.get("score") for d in data if d.get("score") is not None]
            return sum(scores) / len(scores) if scores else 0.0
            
        if "KPI-10" in kpi_name or "Complaint" in kpi_name:
            complaints = sum(float(d.get("complaints", 0)) for d in data)
            meals = sum(float(d.get("meals_served", 10000)) for d in data)
            return (complaints / meals) * 10000 if meals > 0 else 0.0

        if "KPI-9" in kpi_name or "Waste" in kpi_name:
            waste = sum(float(d.get("waste", 0)) for d in data)
            prepared = sum(float(d.get("prepared", 1)) for d in data)
            return (waste / prepared) * 100 if prepared > 0 else 0.0

        # Default: average the 'value' field
        values = [float(d.get("value")) for d in data if d.get("value") is not None]
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def evaluate_breach(actual: float, operator: str, v_min: Optional[float], v_max: Optional[float]) -> bool:
        """Determines if a breach occurred based on the operator and thresholds."""
        # Normalize: ensure v_min is the comparison target for non-range operators
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

    async def get_actuals_from_db(self, contract_id: str, kpi_id: str, kpi_name: str) -> List[Dict]:
        """Fetch historical performance data from MongoDB with fuzzy matching."""
        collection = MongoDB.get_collection("operational_actuals")
        # Extract base code from name if exists (e.g., "KPI-1")
        import re
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
    job = await MongoDB.get_latest_job(contract_id, "kpi")
    if not job:
        return []
    return job.get("result", {}).get("structured", {}).get("kpis", [])

async def seed_actuals_to_db(contract_id: str, actuals_dir: str):
    """Seed local file data into MongoDB operational_actuals collection."""
    collection = MongoDB.get_collection("operational_actuals")
    if not os.path.exists(actuals_dir):
        return
        
    for filename in os.listdir(actuals_dir):
        # Extract base ID like KPI-1 from KPI-1.json or KPI-1.csv
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
            # Clear old actuals for this KPI to avoid duplication
            await collection.delete_many({"contract_id": contract_id, "kpi_id": kpi_id})
            # Insert new ones
            for entry in data:
                entry["contract_id"] = contract_id
                entry["kpi_id"] = kpi_id
                entry["source"] = "manual_seed"
                entry["timestamp"] = entry.get("timestamp", datetime.now().isoformat())
            await collection.insert_many(data)

async def run_monitoring(kpis: List[Dict], contract_id: str):
    engine = BreachEngine()
    
    # Organize KPIs by base ID (e.g., KPI-1)
    kpi_groups = {}
    for kpi in kpis:
        base_id = kpi["kpi_id"]
        if base_id not in kpi_groups:
            kpi_groups[base_id] = {"target": None, "penalties": []}
        
        if kpi["kpi_type"] == "sla":
            kpi_groups[base_id]["target"] = kpi
        elif kpi["kpi_type"] == "penalty":
            kpi_groups[base_id]["penalties"].append(kpi)

    print("\n" + "="*60)
    print("                KPI BREACH MONITORING REPORT (DB-DRIVEN)                ")
    print("="*60)

    for base_id, group in kpi_groups.items():
        target_kpi = group["target"] or (group["penalties"][0] if group["penalties"] else None)
        if not target_kpi: continue

        # Fetch Actuals from DB
        data = await engine.get_actuals_from_db(contract_id, base_id, target_kpi["name"])
        
        if not data:
            print(f"\n[NO DATA] {target_kpi['name']}")
            print(f"  Status: Pending - No data stream found in DB (ID: {base_id})")
            continue

        actual_val = engine.calculate_actual(data, target_kpi["name"])
        unit = target_kpi.get("unit", "")
        
        is_breach = engine.evaluate_breach(
            actual_val, 
            target_kpi["operator"], 
            target_kpi.get("value_min"), 
            target_kpi.get("value_max")
        )
        
        # Prepare threshold display
        display_threshold = f"{target_kpi['operator']} {target_kpi.get('value_min') or target_kpi.get('value_max')}"
        if target_kpi["operator"] == "between":
            display_threshold = f"{target_kpi.get('value_min')} - {target_kpi.get('value_max')}"
        
        status_icon = "[BREACH]" if is_breach else "[OK]"
        print(f"\n{status_icon} {target_kpi['name']}")
        print(f"  Actual: {actual_val:.2f}{unit} | Target: {display_threshold}{unit}")

        if is_breach:
            # Match specific penalty tier
            matched_penalty = None
            for penalty in group["penalties"]:
                triggers = not engine.evaluate_breach(
                    actual_val, 
                    penalty["operator"], 
                    penalty.get("value_min"), 
                    penalty.get("value_max")
                )
                if triggers:
                    matched_penalty = penalty
                    break
            
            if matched_penalty:
                print(f"  Triggered: {matched_penalty['name']}")
                print(f"  Consequence: {matched_penalty['consequence_value']} {matched_penalty['consequence_unit']}")
            else:
                print(f"  Warning: Breach detected but no specific penalty tier matched.")

async def main():
    contract_id = "airport_agreement_2025"
    actuals_dir = "data/actuals"
    
    await MongoDB.connect()
    
    # 1. Sync local files to DB (First-time or Update)
    if os.path.exists(actuals_dir):
        print(f"Syncing local actuals from {actuals_dir} to MongoDB...")
        await seed_actuals_to_db(contract_id, actuals_dir)
    
    # 2. Run monitoring from DB
    kpis = await get_extracted_kpis(contract_id)
    if not kpis:
        print(f"No KPIs found for {contract_id}.")
        return

    await run_monitoring(kpis, contract_id)
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
