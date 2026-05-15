import asyncio
from app.db.mongodb import MongoDB

async def check():
    await MongoDB.connect()
    contract_id = "prod-logistics-v3"
    breaches = await MongoDB.db.breaches.find({"contract_id": contract_id}).to_list(length=100)
    print(f"Found {len(breaches)} breaches for {contract_id}")
    for b in breaches:
        print(f"KPI: {b.get('kpi_id')}, Breach: {b.get('is_breach')}, Value: {b.get('actual_value')}")
        # Check if the KPI metadata in the breach record has the email
        # Actually, the breach record might not have the email directly if it's not in the model.
        # Let's check the KPI vault too.
    
    kpis = await MongoDB.get_kpis(contract_id)
    print(f"\nKPIs in vault for {contract_id}:")
    for k in kpis:
        print(f"ID: {k.get('kpi_id')}, Name: {k.get('name')}, Email: {k.get('contact_email')}")
    
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
