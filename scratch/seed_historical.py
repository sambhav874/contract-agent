
import asyncio
from app.db.mongodb import MongoDB
from app.db.models import OperationalActual
from uuid import uuid4
from datetime import datetime, timedelta
import random

async def seed_historical_actuals():
    await MongoDB.connect()
    contract_id = "logistics_agreement_1.md"
    
    # Clear existing actuals for this contract to avoid duplicates
    await MongoDB.get_collection("actuals").delete_many({"contract_id": contract_id})
    
    kpis = [
        {"id": "KPI-4.1", "name": "Monthly Delivery Volume", "target": 300, "op": ">=", "unit": "goods"},
        {"id": "KPI-4.2a", "name": "Delivery Window SLA", "target": 48, "op": "<=", "unit": "hours"},
        {"id": "KPI-4.2b", "name": "Late Delivery Rate", "target": 5, "op": "<=", "unit": "%"},
        {"id": "KPI-4.3", "name": "Damaged Goods Threshold", "target": 0.2, "op": "<", "unit": "%"},
        {"id": "KPI-4.4", "name": "Order Accuracy Rate", "target": 99, "op": ">=", "unit": "%"},
        {"id": "KPI-4.5", "name": "Safety Compliance Score", "target": 9, "op": ">=", "unit": "score"},
    ]
    
    months = [
        "2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31", "2024-06-15"
    ]
    
    # Performance profile: Jan-Apr (Good), May (Bad), June (Recovering)
    profiles = {
        "2024-01-31": 1.05, # 5% above target/better
        "2024-02-29": 1.02,
        "2024-03-31": 0.98, # slight dip
        "2024-04-30": 1.01,
        "2024-05-31": 0.85, # BREACH MONTH
        "2024-06-15": 0.95  # Recovering
    }
    
    count = 0
    for ts_str in months:
        profile = profiles[ts_str]
        for kpi in kpis:
            # Calculate value based on target and profile
            # For >= ops, value = target * profile
            # For <= ops, value = target / profile (lower is better)
            if kpi["op"] in [">=", ">"]:
                val = kpi["target"] * profile
            else:
                val = kpi["target"] / profile
            
            # Add some randomness
            val = val * (1 + (random.random() - 0.5) * 0.05)
            
            # Rounding
            if kpi["unit"] == "goods": val = int(val)
            else: val = round(val, 2)
            
            actual = OperationalActual(
                actual_id=str(uuid4()),
                contract_id=contract_id,
                kpi_id=kpi["id"],
                value=float(val),
                unit=kpi["unit"],
                timestamp=ts_str + "T12:00:00",
                source="historical_seed"
            )
            await MongoDB.insert_actual(actual.model_dump())
            count += 1

    print(f"Seeded {count} historical actuals.")
    print("Running breach evaluation for all months...")

if __name__ == "__main__":
    asyncio.run(seed_historical_actuals())
