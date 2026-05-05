import asyncio
import sys
import os
import click
from rich.console import Console
from rich.panel import Panel

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.mongodb import MongoDB
from app.agents.event_agent import EventAgent
from scripts.check_breaches import BreachEngine, get_extracted_kpis

console = Console()

@click.command()
@click.option("--text", prompt="Event Description", help="The unstructured event text (e.g., from an email or invoice)")
@click.option("--contract-id", default="airport_agreement_2025", help="The contract to check against")
def process_event_cli(text: str, contract_id: str):
    """Process an operational event and check for contractual breaches."""
    
    async def _run():
        await MongoDB.connect()
        
        # 1. Fetch KPIs
        kpis = await get_extracted_kpis(contract_id)
        if not kpis:
            console.print(f"[red]No KPIs found for {contract_id}[/red]")
            return

        # 2. Map Event to KPI via Agent
        agent = EventAgent()
        console.print(f"\n[bold blue]Analysing Event:[/bold blue] {text}")
        with console.status("[bold green]Agent mapping event to contractual KPIs..."):
            analysis = await agent.process_event(text, kpis)

        if not analysis.mappings:
            console.print("[yellow]Event does not appear relevant to any contractual KPIs.[/yellow]")
            return

        # 3. Check Breaches
        engine = BreachEngine()
        
        for mapping in analysis.mappings:
            # Find the actual KPI object from our inventory
            kpi = next((k for k in kpis if k["kpi_id"] == mapping.kpi_id or mapping.kpi_id in k["name"]), None)
            
            if not kpi:
                console.print(f"[yellow]Mapped to unknown KPI ID: {mapping.kpi_id}[/yellow]")
                continue

            console.print(Panel(
                f"[bold]KPI Match:[/bold] {kpi['name']}\n"
                f"[bold]Reasoning:[/bold] {mapping.reasoning}\n"
                f"[bold]Extracted Actual:[/bold] {mapping.actual_value} {mapping.unit}",
                title="Semantic Mapping Result",
                border_style="blue"
            ))

            is_breach = engine.evaluate_breach(
                mapping.actual_value,
                kpi["operator"],
                kpi.get("value_min"),
                kpi.get("value_max")
            )

            if is_breach:
                console.print(f"[bold red]!! BREACH DETECTED !![/bold red]")
                console.print(f"Target: {kpi['operator']} {kpi['value_min']} {kpi['unit']}")
                console.print(f"Actual: {mapping.actual_value} {mapping.unit}")
            else:
                console.print(f"[bold green]✓ COMPLIANT[/bold green]")
                console.print(f"Actual {mapping.actual_value} is within threshold {kpi['operator']} {kpi['value_min']}")

        await MongoDB.disconnect()

    asyncio.run(_run())

if __name__ == "__main__":
    process_event_cli()
