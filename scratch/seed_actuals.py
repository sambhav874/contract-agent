
import asyncio
from app.db.mongodb import MongoDB
from app.db.models import OperationalActual
from uuid import uuid4
from datetime import datetime

async def seed_actuals():
    await MongoDB.connect()
    contract_id = "logistics_agreement_1.md"
    
    actuals = [
        # April (On track)
        {"kpi_id": "KPI-4.1", "value": 310, "unit": "goods", "timestamp": "2024-04-30T23:59:59"},
        {"kpi_id": "KPI-4.2a", "value": 42, "unit": "hours", "timestamp": "2024-04-30T23:59:59"},
        {"kpi_id": "KPI-4.2b", "value": 3, "unit": "%", "timestamp": "2024-04-30T23:59:59"},
        {"kpi_id": "KPI-4.3", "value": 0.1, "unit": "%", "timestamp": "2024-04-30T23:59:59"},
        {"kpi_id": "KPI-4.4", "value": 99.5, "unit": "%", "timestamp": "2024-04-30T23:59:59"},
        {"kpi_id": "KPI-4.5", "value": 9.5, "unit": "score", "timestamp": "2024-04-30T23:59:59"},
        
        # May (Breaches)
        {"kpi_id": "KPI-4.1", "value": 250, "unit": "goods", "timestamp": "2024-05-13T12:00:00"},
        {"kpi_id": "KPI-4.2a", "value": 52, "unit": "hours", "timestamp": "2024-05-13T12:00:00"},
        {"kpi_id": "KPI-4.2b", "value": 7, "unit": "%", "timestamp": "2024-05-13T12:00:00"},
        {"kpi_id": "KPI-4.3", "value": 0.5, "unit": "%", "timestamp": "2024-05-13T12:00:00"},
        {"kpi_id": "KPI-4.4", "value": 98.0, "unit": "%", "timestamp": "2024-05-13T12:00:00"},
        {"kpi_id": "KPI-4.5", "value": 8.5, "unit": "score", "timestamp": "2024-05-13T12:00:00"},
    ]
    
    for item in actuals:
        actual = OperationalActual(
            actual_id=str(uuid4()),
            contract_id=contract_id,
            kpi_id=item["kpi_id"],
            value=float(item["value"]),
            unit=item["unit"],
            timestamp=item["timestamp"],
            source="seed_script"
        )
        await MongoDB.insert_actual(actual.model_dump())
        print(f"Inserted actual for {item['kpi_id']}: {item['value']} {item['unit']}")

    print("Seeding completed.")

if __name__ == "__main__":
    asyncio.run(seed_actuals())
