import asyncio
import os
import sys
from rich.console import Console

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.mongodb import MongoDB
from cli import ingest, analyse, save_kpis, ingest_event, check_breaches

console = Console()

async def run_test_flow():
    contract_path = "tests/fixtures/contracts/airport_food.md"
    contract_id = "TEST-AIRPORT-001"

    console.rule("[bold blue]1. Ingesting Contract")
    # Using the cli functions directly or via run_command?
    # Better to run via shell to simulate real usage.
    os.system(f"./venv/bin/python3 cli.py ingest {contract_path} --id {contract_id} --overwrite")

    console.rule("[bold blue]2. Analysing KPIs")
    os.system(f"./venv/bin/python3 cli.py analyse {contract_id} --intent kpi --sync")

    console.rule("[bold blue]3. Saving KPIs to Vault")
    os.system(f"./venv/bin/python3 cli.py save-kpis {contract_id}")

    console.rule("[bold blue]4. Ingesting Events (Actuals)")
    # Event 1: Temperature breach (Hot meal too cold)
    event_1 = "Daily Food Safety Log: Flight BA123 hot meal temperature recorded at 110F during service."
    os.system(f'./venv/bin/python3 cli.py ingest-event {contract_id} "{event_1}"')

    # Event 2: Delivery Delay breach (6 hours delay)
    event_2 = "Logistics Report: Shipment #9928 for flight CX882 arrived 6 hours before departure, which is outside the 4-hour catering window."
    os.system(f'./venv/bin/python3 cli.py ingest-event {contract_id} "{event_2}"')

    console.rule("[bold blue]5. Checking Breaches")
    os.system(f"./venv/bin/python3 cli.py check-breaches {contract_id}")

if __name__ == "__main__":
    asyncio.run(run_test_flow())
