import asyncio
import os
import sys
import time
import random
from rich.console import Console
from rich.live import Live
from rich.table import Table

# Add current directory to path
sys.path.append(os.getcwd())

console = Console()

def get_breach_table(contract_id):
    # We call the CLI to get the latest state
    # In a real app, we would use the DB directly
    import subprocess
    result = subprocess.run(
        [f"./venv/bin/python3", "cli.py", "check-breaches", contract_id],
        capture_output=True, text=True
    )
    return result.stdout

async def simulate_stream():
    contract_id = "TEST-AIRPORT-001"
    
    # Real KPI IDs from the vault
    kpi_pool = [
        {"id": "kpi_006_hot", "name": "Hot Meal Temp", "unit": "F", "normal": (145, 160), "breach": (110, 130)},
        {"id": "kpi_013_target", "name": "Equipment Uptime", "unit": "%", "normal": (98, 100), "breach": (90, 97)},
        {"id": "kpi_002_early", "name": "Delivery Window", "unit": "hours", "normal": (1, 3), "breach": (5, 8)},
    ]
    
    console.print(f"[bold green]Starting Deterministic KPI Stream Monitor for {contract_id}...[/bold green]")
    console.print("[dim]Simulating incoming structured data from ERP/Sensors...[/dim]\n")
    
    for i in range(5):
        kpi = random.choice(kpi_pool)
        # 30% chance of breach
        is_breach = random.random() < 0.3
        val_range = kpi["breach"] if is_breach else kpi["normal"]
        value = round(random.uniform(*val_range), 1)
        
        console.print(f"[blue]📥 Incoming Data Packet {i+1}:[/blue] KPI={kpi['name']} Value={value}{kpi['unit']}")
        
        # Ingest using structured command
        os.system(f'./venv/bin/python3 cli.py ingest-actuals {contract_id} --kpi-id {kpi["id"]} --value {value} --unit {kpi["unit"]} > /dev/null 2>&1')
        
        # Check
        console.print("[yellow]🔍 Processing breach detection...[/yellow]")
        os.system(f'./venv/bin/python3 cli.py check-breaches {contract_id}')
        
        console.print("-" * 50)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(simulate_stream())
