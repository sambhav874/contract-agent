
import asyncio
from app.db.mongodb import MongoDB

async def check_breach_remediations():
    await MongoDB.connect()
    breaches_col = MongoDB.get_collection("breaches")
    
    breaches = await breaches_col.find({"contract_id": "logistics_agreement_1.md"}).to_list(100)
    print(f"Found {len(breaches)} breaches for logistics_agreement_1.md:")
    for b in breaches:
        is_breach = b.get("is_breach")
        status = "BREACH" if is_breach else "OK"
        print(f" - KPI: {b.get('kpi_id')} | Status: {status}")
        if is_breach:
            print(f"   * Remediation: {b.get('remediation')}")
            print(f"   * SLA: {b.get('remediation_sla')}")

if __name__ == "__main__":
    asyncio.run(check_breach_remediations())
