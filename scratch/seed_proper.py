
import asyncio
from app.db.mongodb import MongoDB
from app.db.models import OperationalActual
from uuid import uuid4
from datetime import datetime, timedelta
import random

async def seed_proper_data():
    await MongoDB.connect()
    contract_id = "logistics_agreement_1.md"
    
    # Clear existing actuals for this contract
    await MongoDB.get_collection("actuals").delete_many({"contract_id": contract_id})
    
    kpis = [
        {"id": "KPI-4.1", "target": 300, "op": ">=", "unit": "goods"},
        {"id": "KPI-4.2a", "target": 48, "op": "<=", "unit": "hours"},
        {"id": "KPI-4.2b", "target": 5, "op": "<=", "unit": "%"},
        {"id": "KPI-4.3", "target": 0.2, "op": "<", "unit": "%"},
        {"id": "KPI-4.4", "target": 99, "op": ">=", "unit": "%"},
        {"id": "KPI-4.5", "target": 9, "op": ">=", "unit": "score"},
    ]
    
    # Daily data for the last 30 days
    start_date = datetime.now() - timedelta(days=30)
    
    count = 0
    for i in range(31):
        curr_date = start_date + timedelta(days=i)
        ts = curr_date.isoformat()
        
        # Determine if this day is a "bad day" (mostly around May 10-15)
        is_bad_period = 10 <= curr_date.day <= 15 and curr_date.month == 5
        
        for kpi in kpis:
            profile = 0.85 if is_bad_period else 1.05
            
            if kpi["op"] in [">=", ">"]:
                val = kpi["target"] * profile
            else:
                val = kpi["target"] / profile
                
            val = val * (1 + (random.random() - 0.5) * 0.1)
            
            if kpi["unit"] == "goods": val = int(val)
            else: val = round(val, 3)
            
            actual = OperationalActual(
                actual_id=str(uuid4()),
                contract_id=contract_id,
                kpi_id=kpi["id"],
                value=float(val),
                unit=kpi["unit"],
                timestamp=ts,
                source="proper_seed"
            )
            await MongoDB.insert_actual(actual.model_dump())
            count += 1

    print(f"Seeded {count} daily actuals for the last 30 days.")

if __name__ == "__main__":
    asyncio.run(seed_proper_data())
