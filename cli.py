#!/usr/bin/env python3
"""CLI entry point for Contract Intelligence Agent."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.config import settings
from app.db.mongodb import MongoDB
from app.db.models import AnalysisJob
from app.ingestion.parser import parse_contract
from app.ingestion.chunker import hierarchical_chunk
from app.ingestion.embedder import get_embedding_service


console = Console()


@click.group()
def cli():
    """Contract Intelligence Agent - CLI for legal contract analysis."""
    pass


@cli.command()
@click.argument("file_path")
@click.option("--name", "-n", help="Contract name")
@click.option("--async", "is_async", default=False, help="Run asynchronously")
def ingest(file_path: str, name: str | None, is_async: bool = False):
    """Ingest a contract file."""
    console.print(f"[bold blue]Ingesting:[/bold blue] {file_path}")

    # Parse contract
    contract_metadata, structural_map = asyncio.run(parse_contract(file_path, name))

    with open(file_path, "r") as f:
        text = f.read()

    # Create chunks
    chunks = hierarchical_chunk(text, contract_metadata.contract_id, structural_map)

    console.print(f"  [green]✓[/green] Parsed {len(structural_map.sections)} sections")
    console.print(f"  [green]✓[/green] Created {len(chunks)} chunks")

    # Embed chunks
    embedder = get_embedding_service()
    embedded_chunks = asyncio.run(embedder.embed_chunks(chunks))

    console.print(f"  [green]✓[/green] Embedded {len(embedded_chunks)} chunks")

    # Store in MongoDB
    async def save_to_db():
        await MongoDB.connect()
        await MongoDB.insert_contract(contract_metadata)
        await MongoDB.insert_chunks(embedded_chunks)

    asyncio.run(save_to_db())

    console.print(f"  [green]✓[/green] Stored in MongoDB")
    console.print(f"\n[bold]Contract ID:[/bold] {contract_metadata.contract_id}")
    console.print(f"[bold]Name:[/bold] {contract_metadata.name}")


@cli.command()
def list():
    """List all ingested contracts."""
    async def _list():
        await MongoDB.connect()
        contracts = await MongoDB.list_contracts()
        return contracts

    contracts = asyncio.run(_list())

    if not contracts:
        console.print("[yellow]No contracts found.[/yellow]")
        return

    table = Table(title="Contracts")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Type", style="blue")
    table.add_column("Created", style="dim")

    for contract in contracts:
        created = contract.get("created_at")
        table.add_row(
            contract.get("contract_id", "")[:8] + "...",
            contract.get("name", "Unknown"),
            contract.get("contract_type", "Unknown"),
            created.strftime("%Y-%m-%d") if created else "",
        )

    console.print(table)


@cli.command()
@click.argument("contract_id")
@click.option("--intent", "-i", required=True, help="Analysis intent")
@click.option("--q", help="Free-text query")
@click.option("--sync", is_flag=True, default=False, help="Run synchronously")
@click.option("--mode", default="plain", help="Analysis mode (plain/legal)")
def analyse(contract_id: str, intent: str, q: str | None = None, sync: bool = False, mode: str = "plain"):
    """Run analysis on a contract."""
    console.print(f"[bold blue]Analyzing:[/bold blue] {contract_id}")
    console.print(f"[bold]Intent:[/bold] {intent}")

    if q:
        console.print(f"[bold]Query:[/bold] {q}")

    if sync:
        # Sync mode - run everything in one event loop
        async def _run_sync():
            from app.routing.intent_router import route_intent
            from app.agents.risk_agent import RiskAgent
            from app.agents.kpi_agent import KPIAgent
            from app.agents.clause_agent import ClauseAgent
            from app.agents.obligation_agent import ObligationAgent
            from app.agents.summary_agent import SummaryAgent
            from app.agents.redflag_agent import RedFlagAgent
            from app.synthesis.synthesiser import synthesise_output

            await MongoDB.connect()

            # Create job
            job_id = str(uuid.uuid4())
            job_data = {
                "job_id": job_id,
                "contract_id": contract_id,
                "intent": intent,
                "user_query": q,
                "status": "running",
                "created_at": datetime.now(timezone.utc),
            }
            await MongoDB.insert_analysis_job(job_data)

            # Get contract metadata for structural map
            contract_meta = await MongoDB.get_contract(contract_id)
            struct_map = None
            if contract_meta and "structural_map" in contract_meta:
                from app.db.models import StructuralMap
                struct_map = StructuralMap.model_validate(contract_meta["structural_map"])

            # Route intent
            query_plan = await route_intent(intent, q, structural_map=struct_map)

            # Select agent
            agent_map = {
                "risk": RiskAgent,
                "kpi": KPIAgent,
                "clause": ClauseAgent,
                "obligations": ObligationAgent,
                "summary": SummaryAgent,
                "redflags": RedFlagAgent,
            }

            agent_class = agent_map.get(intent, RiskAgent)
            agent = agent_class()

            # Run analysis
            output = await agent.analyze(query_plan, contract_id, q or "")

            # Synthesize
            result = await synthesise_output(output)

            # Update job in DB
            await MongoDB.update_analysis_job(job_id, {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now(timezone.utc)
            })

            return result

        console.print("[yellow]Running analysis (this may take a moment)...[/yellow]")
        try:
            result = asyncio.run(_run_sync())
            console.print("[green]✓ Analysis complete and persisted to database[/green]")
            _display_analysis_result(result, intent)
        except Exception as e:
            import traceback
            traceback.print_exc()
            console.print(f"[red]Error: {str(e)}[/red]")
    else:
        # Async mode - just create job and return
        async def _save_job():
            await MongoDB.connect()
            job_id = str(uuid.uuid4())
            job_data = {
                "job_id": job_id,
                "contract_id": contract_id,
                "intent": intent,
                "user_query": q,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
            }
            await MongoDB.insert_analysis_job(job_data)
            return job_id

        job_id = asyncio.run(_save_job())
        console.print(f"\n[bold]Job submitted.[/bold]")
        console.print(f"Job ID: {job_id}")
        console.print(f"Check status: python cli.py status {job_id}")


@cli.command()
@click.argument("contract_id")
@click.option("--q", required=True, help="Question to answer")
def query(contract_id: str, q: str):
    """Ask a question about a contract."""
    console.print(f"[bold blue]Contract:[/bold blue] {contract_id}")
    console.print(f"[bold blue]Question:[/bold blue] {q}")

    console.print("[yellow]Query functionality coming soon.[/yellow]")


@cli.command()
@click.argument("job_id")
def status(job_id: str):
    """Check job status."""
    async def _status():
        await MongoDB.connect()
        return await MongoDB.get_analysis_job(job_id)

    job = asyncio.run(_status())

    if not job:
        console.print(f"[red]Job {job_id} not found.[/red]")
        return

    console.print(f"[bold]Job ID:[/bold] {job['job_id']}")
    console.print(f"[bold]Status:[/bold] {job['status']}")
    console.print(f"[bold]Intent:[/bold] {job['intent']}")

    if job["status"] == "completed" and job.get("result"):
        console.print("\n[bold]Result:[/bold]")
        console.print(json.dumps(job["result"], indent=2))
    elif job["status"] == "failed":
        console.print(f"[red]Error:[/red] {job.get('error_message', 'Unknown error')}")


@cli.command()
@click.argument("identifier")
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json", help="Output format")
@click.option("--output", "-o", help="Output file path")
@click.option("--intent", "-i", default="kpi", help="Intent to export (if identifier is a contract_id)")
def export(identifier: str, fmt: str = "json", output: str | None = None, intent: str = "kpi"):
    """Export analysis results by Job ID or Contract ID."""
    async def _export():
        await MongoDB.connect()
        # Try as Job ID first
        job = await MongoDB.get_analysis_job(identifier)
        if not job:
            # Try as Contract ID
            job = await MongoDB.get_latest_job(identifier, intent)
        return job

    job = asyncio.run(_export())

    if not job:
        console.print(f"[red]No completed job found for {identifier} (intent: {intent})[/red]")
        return

    result = job.get("result", {})
    if not result:
        console.print("[red]Job has no result data.[/red]")
        return

    if output:
        _save_result_to_file(result, output, fmt)
    else:
        if fmt == "json":
            console.print(json.dumps(result, indent=2))
        else:
            # For CSV without output file, just print a preview or error
            console.print("[yellow]CSV export requires an output file path using --output or -o[/yellow]")


@cli.command()
@click.argument("contract_id")
def delete(contract_id: str):
    """Delete a contract."""
    console.print("[yellow]Delete functionality coming soon.[/yellow]")


def _display_analysis_result(result: dict[str, Any], intent: str) -> None:
    """Display analysis results using Rich."""
    if intent == "risk":
        _display_risk_result(result)
    elif intent == "kpi":
        _display_kpi_result(result)
    else:
        console.print(json.dumps(result, indent=2))


def _display_risk_result(result: dict[str, Any]) -> None:
    """Display risk analysis results."""
    structured = result.get("structured", {})
    narrative = result.get("narrative", "")

    # Overall score
    overall_score = structured.get("overall_risk_score", 0)
    risk_grade = structured.get("risk_grade", "?")

    console.print(Panel(f"[bold]Risk Grade: {risk_grade}[/bold]\nScore: {overall_score}/10"))

    # Risks table
    risks = structured.get("risks", [])
    if risks:
        table = Table(title="Risks")
        table.add_column("Severity", style="red")
        table.add_column("Type")
        table.add_column("Section")
        table.add_column("Explanation")

        for risk in risks:
            severity = risk.get("severity", 0)
            color_map = {5: "red", 4: "orange", 3: "yellow", 2: "blue", 1: "green"}
            color = color_map.get(severity, "white")

            table.add_row(
                f"[{color}]{'█' * severity}[/{color}]",
                risk.get("risk_type", ""),
                risk.get("section", ""),
                risk.get("explanation", "")[:100] + "...",
            )

        console.print(table)

    # Narrative
    if narrative:
        console.print(Panel(narrative, title="Summary"))


def _display_kpi_result(result: dict[str, Any]) -> None:
    """Display KPI results."""
    structured = result.get("structured", {})
    kpis = structured.get("kpis", [])

    if kpis:
        table = Table(title="Key Performance Indicators", show_lines=True)
        table.add_column("Name", style="cyan", no_wrap=False)
        table.add_column("Value", style="green")
        table.add_column("Unit", style="dim")
        table.add_column("Type", style="blue")
        table.add_column("Party", style="magenta")
        table.add_column("Trigger Condition", style="yellow")
        table.add_column("Confidence", style="dim")

        for kpi in kpis:
            conf = kpi.get("confidence", 0.0)
            conf_str = f"{conf:.2f}"
            if conf > 0.9:
                conf_str = f"[green]{conf_str}[/green]"
            elif conf < 0.7:
                conf_str = f"[red]{conf_str}[/red]"

            table.add_row(
                kpi.get("name", ""),
                kpi.get("value", ""),
                kpi.get("unit", ""),
                kpi.get("kpi_type", ""),
                kpi.get("party", ""),
                kpi.get("trigger_condition", "")[:100],
                conf_str,
            )

        console.print(table)
    else:
        console.print("[yellow]No specific KPIs found in this contract context.[/yellow]")
    
    # Financial Summary
    fin_summary = structured.get("financial_summary", "")
    if fin_summary:
        console.print(Panel(fin_summary, title="Financial Summary"))
        
    # Penalties
    penalties = structured.get("penalties", [])
    if penalties:
        p_text = "\n".join([f"• {p}" for p in penalties])
        console.print(Panel(p_text, title="Penalty Structure"))


def _save_result_to_file(result: dict[str, Any], filename: str, fmt: str) -> None:
    """Save analysis results to a file."""
    try:
        if fmt == "json":
            with open(filename, "w") as f:
                json.dump(result, f, indent=2)
        elif fmt == "csv":
            import csv
            structured = result.get("structured", {})
            kpis = structured.get("kpis", [])
            
            if not kpis:
                console.print("[yellow]No KPIs to save to CSV.[/yellow]")
                return
                
            keys = kpis[0].keys()
            with open(filename, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(kpis)
        
        console.print(f"[green]✓ Saved to {filename}[/green]")
    except Exception as e:
        console.print(f"[red]Error saving file: {str(e)}[/red]")


if __name__ == "__main__":
    cli()
