
import asyncio
import httpx

async def run_extraction():
    async with httpx.AsyncClient(timeout=300) as client:
        # Ingest
        resp = await client.post("http://localhost:8000/contracts/ingest", json={"filename": "logistics_agreement_v3_production.md"})
        contract_id = resp.json()["contract_id"]
        print(f"Ingested: {contract_id}")
        
        # Extract
        print("Extracting KPIs...")
        await client.post(f"http://localhost:8000/contracts/{contract_id}/extract-kpis")
        print("Done.")

if __name__ == "__main__":
    asyncio.run(run_extraction())
