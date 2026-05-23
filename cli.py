#!/usr/bin/env python3
"""CLI entry point for Contract Intelligence Agent."""

import asyncio
import json
import csv
import time
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
@click.option("--port", default=8000, help="Port to run the server on")
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
def serve(port: int, host: str):
    """Start the Contract Guardian API server."""
    import uvicorn
    console.print(f"[bold green]Starting Contract Guardian API on {host}:{port}...[/bold green]")
    uvicorn.run("app.api:app", host=host, port=port, reload=True)



@cli.command()
@click.argument("file_path")
@click.option("--name", "-n", help="Contract name")
@click.option("--id", "contract_id_opt", help="Override contract ID")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing contract and chunks")
@click.option("--async", "is_async", default=False, help="Run asynchronously (legacy)")
def ingest(file_path: str, name: str | None = None, contract_id_opt: str | None = None, overwrite: bool = False, is_async: bool = False):
    """Ingest a contract file."""
    console.print(f"[bold blue]Ingesting:[/bold blue] {file_path}")

    # Parse contract
    contract_metadata, structural_map, text = asyncio.run(parse_contract(file_path, name))

    # Override ID if provided
    if contract_id_opt:
        contract_metadata.contract_id = contract_id_opt

    # Create chunks
    chunks = hierarchical_chunk(text, contract_metadata.contract_id, structural_map)

    console.print(f"  [green]✓[/green] Parsed {len(structural_map.sections)} sections")
    console.print(f"  [green]✓[/green] Created {len(chunks)} chunks")

    async def _run_ingestion():
        await MongoDB.connect()

        # Handle overwrite
        existing = await MongoDB.get_contract(contract_metadata.contract_id)
        if existing:
            if not overwrite:
                console.print(f"[yellow]Contract {contract_metadata.contract_id} already exists. Use --overwrite to replace.[/yellow]")
                return
            console.print(f"[yellow]Overwriting existing contract {contract_metadata.contract_id}...[/yellow]")
            await MongoDB.delete_contract(contract_metadata.contract_id)

        # Embed
        embedder = get_embedding_service()
        embedded_chunks = await embedder.embed_chunks(chunks)
        console.print(f"  [green]✓[/green] Embedded {len(embedded_chunks)} chunks")

        # Store in MongoDB
        await MongoDB.insert_contract(contract_metadata)
        await MongoDB.insert_chunks(embedded_chunks)

        await MongoDB.disconnect()

    asyncio.run(_run_ingestion())

    console.print(f"  [green]✓[/green] Stored in MongoDB")
    console.print(f"\n[bold]Contract ID:[/bold] {contract_metadata.contract_id}")
    console.print(f"[bold]Name:[/bold] {contract_metadata.name}")


@cli.command(name="list")
def list_contracts():
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
@click.option("--csv", help="Path to save results as CSV")
def analyse(contract_id: str, intent: str, q: str | None = None, sync: bool = False, mode: str = "plain", csv: str | None = None):
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

            # Auto-export to CSV if requested
            if csv:
                _save_result_to_file(result, csv, "csv")

            return result

        console.print("[yellow]Running analysis (this may take a moment)...[/yellow]")
        try:
            result = asyncio.run(_run_sync())
            console.print("[green]✓ Analysis complete and persisted to database[/green]")
            _display_analysis_result(result, intent)

            # Auto-save to local JSON so results are always on disk
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_path = Path(f"results_{contract_id}_{intent}_{ts}.json")
            try:
                with open(auto_path, "w") as f:
                    json.dump(result, f, indent=2, default=str)
                console.print(f"[dim]Results saved → {auto_path}[/dim]")
                console.print(
                    f"[dim]To export later: python cli.py export {contract_id} --intent {intent} -o out.json[/dim]"
                )
            except Exception:
                pass
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


@cli.command()
@click.argument("contract_id")
@click.option(
    "--csv", "csv_path",
    default="data/kpis/exhaustive_kpis.csv",
    show_default=True,
    help="Ground-truth KPI CSV to evaluate against.",
)
@click.option(
    "--output", "-o",
    default="reports/evaluation/evaluation_results_rag.json",
    show_default=True,
    help="Path to write the evaluation report JSON.",
)
@click.option(
    "--max-samples", default=20, show_default=True,
    help="Maximum KPI rows to evaluate (keeps cost low).",
)
@click.option(
    "--top-k", default=10, show_default=True,
    help="Chunks retrieved per question.",
)
def evaluate(contract_id: str, csv_path: str, output: str, max_samples: int, top_k: int):
    """
    Run RAG evaluation for a contract against a ground-truth KPI CSV.

    Evaluates four metrics using Gemini as the judge LLM:

      \b
      • Faithfulness      — Are answers grounded in the retrieved context?
      • Answer Relevance  — Does the answer address the question?
      • Context Recall    — Are ground-truth facts present in context?
      • Context Precision — Are retrieved chunks actually useful?

    Results are printed to the terminal AND saved to --output.
    """
    from app.evaluation.rag_evaluator import RAGEvaluator

    csv_file = Path(csv_path)
    if not csv_file.exists():
        console.print(f"[red]CSV not found: {csv_path}[/red]")
        console.print("Provide --csv path to a KPI ground-truth file.")
        return

    async def _run():
        await MongoDB.connect()
        evaluator = RAGEvaluator()
        console.print(
            f"[bold blue]Evaluating:[/bold blue] {contract_id}\n"
            f"[dim]CSV: {csv_path} | top_k={top_k} | max_samples={max_samples}[/dim]"
        )
        t0 = time.perf_counter()
        report = await evaluator.evaluate_from_csv(
            csv_path=str(csv_file),
            contract_id=contract_id,
            top_k=top_k,
            max_samples=max_samples,
        )
        elapsed = round(time.perf_counter() - t0, 1)
        return report, elapsed

    try:
        report, elapsed = asyncio.run(_run())
    except Exception as e:
        import traceback
        traceback.print_exc()
        console.print(f"[red]Evaluation failed: {e}[/red]")
        return

    # ── Pretty-print summary table ────────────────────────────────────
    from rich.table import Table as RTable
    table = RTable(title=f"RAG Evaluation — {contract_id}", show_lines=True)
    table.add_column("Metric",            style="cyan",   no_wrap=True)
    table.add_column("Score (0–1)",       style="green",  justify="right")
    table.add_column("What it measures",  style="dim")

    rows = [
        ("Faithfulness",      report.mean_faithfulness,      "Claims in answer are grounded in context"),
        ("Answer Relevance",  report.mean_answer_relevance,  "Answer actually addresses the question"),
        ("Context Recall",    report.mean_context_recall,    "Ground-truth facts present in context"),
        ("Context Precision", report.mean_context_precision, "Retrieved chunks are useful (low noise)"),
        ("Aggregate",         report.mean_aggregate,         "Weighted composite (faith 35% + rest 25/20/20%)"),
    ]
    for label, score, desc in rows:
        color = "green" if score >= 0.75 else ("yellow" if score >= 0.5 else "red")
        table.add_row(label, f"[{color}]{score:.3f}[/{color}]", desc)

    console.print(table)
    console.print(
        f"[dim]Evaluated {len(report.samples)} samples in {elapsed}s[/dim]\n"
        f"[dim]Per-sample detail → {output}[/dim]"
    )

    # ── Save full report ──────────────────────────────────────────────
    out_path = Path(output)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2, default=str)
        console.print(f"[green]✓ Full report saved → {out_path.resolve()}[/green]")
    except Exception as e:
        console.print(f"[red]Could not save report: {e}[/red]")


@cli.command()
@click.argument("contract_id")
@click.option(
    "--csv", "csv_path",
    default="data/kpis/exhaustive_kpis.csv",
    show_default=True,
    help="Ground-truth KPI CSV to evaluate against.",
)
@click.option(
    "--max-samples", default=10, show_default=True,
    help="Maximum KPI rows to evaluate.",
)
def evaluate_ragas(contract_id: str, csv_path: str, max_samples: int):
    """
    Run the Ragas RAG evaluation (Faithfulness, Relevance, Precision, Recall).

    Phase 1 (async):  retrieve contexts + generate answers.
    Phase 2 (sync):   call ragas.evaluate() outside any event loop.
    """
    import csv
    from app.evaluation.ragas_eval import RagasEvaluator

    csv_file = Path(csv_path)
    if not csv_file.exists():
        console.print(f"[red]CSV not found: {csv_path}[/red]")
        return

    # --- Load test set from CSV ----------------------------------------- #
    test_set = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name  = row.get("name",   row.get("KPI Name", ""))
            val   = row.get("value",  row.get("Value", ""))
            unit  = row.get("unit",   row.get("Unit", ""))
            # clause_text gives Ragas a real sentence to compare against retrieved context.
            # Fallback to "name is value unit" if clause_text is absent.
            clause = row.get("clause_text", "").strip()
            trigger = row.get("trigger_condition", "").strip()
            if clause:
                ground_truth = clause
            elif trigger:
                ground_truth = f"{name}: {val} {unit}. Condition: {trigger}".strip()
            else:
                ground_truth = f"{name} is {val} {unit}".strip()

            if name and val:
                test_set.append({
                    "query":  f"What is the {name} KPI in this contract?",
                    "answer": ground_truth,
                })
            if len(test_set) >= max_samples:
                break


    if not test_set:
        console.print("[yellow]No valid samples found in CSV.[/yellow]")
        return

    console.print(f"[bold blue]Ragas Eval:[/bold blue] {contract_id} — {len(test_set)} sample(s)")
    evaluator = RagasEvaluator()

    # --- Phase 1: async retrieval + generation (NO ragas inside here) --- #
    console.print("[dim]Phase 1: retrieving contexts and generating answers…[/dim]")
    try:
        dataset = asyncio.run(evaluator.build_eval_dataset(contract_id, test_set))
    except Exception as e:
        import traceback; traceback.print_exc()
        console.print(f"[red]Retrieval/generation failed: {e}[/red]")
        return

    # --- Phase 2: synchronous ragas.evaluate() (outside asyncio.run) ---- #
    console.print("[dim]Phase 2: scoring with Ragas…[/dim]")
    try:
        report = evaluator.score(dataset)
    except Exception as e:
        import traceback; traceback.print_exc()
        console.print(f"[red]Ragas scoring failed: {e}[/red]")
        return

    # --- Display results ------------------------------------------------- #
    agg = report["aggregate_scores"]
    if agg:
        console.print("\n[bold]Aggregate Metrics:[/bold]")
        for metric_name, score in agg.items():
            bar = "█" * int((score or 0) * 20)
            console.print(f"  {metric_name:<25} {score:.4f}  {bar}")
    else:
        console.print("[yellow]No scores returned — Ragas jobs may have timed out.[/yellow]")

    details = report.get("details", [])
    if details:
        table = Table(title="Ragas Detailed Results", show_lines=True)
        table.add_column("Query", style="cyan", max_width=40)
        table.add_column("Faithfulness", style="magenta", justify="center")
        table.add_column("Relevance",    style="magenta", justify="center")
        table.add_column("Precision",    style="yellow",  justify="center")
        table.add_column("Recall",       style="yellow",  justify="center")

        for d in details:
            def fmt(v):
                return f"{v:.2f}" if isinstance(v, float) else str(v)
            table.add_row(
                (d.get("question", "")[:40] + "…"),
                fmt(d.get("faithfulness", float("nan"))),
                fmt(d.get("answer_relevancy", float("nan"))),
                fmt(d.get("context_precision", float("nan"))),
                fmt(d.get("context_recall", float("nan"))),
            )
        console.print(table)


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


@cli.command()
@click.argument("contract_id")
def save_kpis(contract_id: str):
    """Save extracted KPIs from the latest analysis to permanent storage."""
    async def _run():
        await MongoDB.connect()
        job = await MongoDB.get_latest_job(contract_id, "kpi")
        if not job:
            console.print("[red]No completed KPI analysis found for this contract.[/red]")
            return

        kpis = job.get("result", {}).get("structured", {}).get("kpis", [])
        if not kpis:
            console.print("[yellow]No KPIs found in analysis result.[/yellow]")
            return

        count = await MongoDB.upsert_kpis(contract_id, kpis)
        console.print(f"[green]✓ Persisted {count} KPIs to the vault.[/green]")

    asyncio.run(_run())


@cli.command()
@click.argument("contract_id")
def check_breaches(contract_id: str):
    """Compare all actuals against KPI targets and detect breaches."""
    from app.agents.breach_engine import BreachEngine

    async def _run():
        await MongoDB.connect()
        kpis = await MongoDB.get_kpis(contract_id)
        actuals_raw = await MongoDB.get_all_actuals(contract_id)

        if not kpis:
            console.print("[red]No KPIs found for this contract.[/red]")
            return
        if not actuals_raw:
            console.print("[yellow]No actual performance data found.[/yellow]")
            return

        # Map kpis by id for easy lookup (Normalized to lowercase/snake_case)
        def normalize_id(idx):
            return str(idx).lower().replace("-", "_")

        kpi_map = {normalize_id(k["kpi_id"]): k for k in kpis}

        # Aggregate (Average) actuals across the period
        actuals_by_kpi = {}
        for a in actuals_raw:
            norm_id = normalize_id(a["kpi_id"])
            if norm_id not in actuals_by_kpi:
                actuals_by_kpi[norm_id] = []
            actuals_by_kpi[norm_id].append(a)

        actuals = []
        for norm_id, data in actuals_by_kpi.items():
            kpi = kpi_map.get(norm_id)
            if not kpi: continue

            agg_type = kpi.get("aggregation_type", "avg")
            vals = [float(d.get("value", 0)) for d in data]

            if agg_type == "sum":
                final_val = sum(vals)
            elif agg_type == "min":
                final_val = min(vals) if vals else 0
            elif agg_type == "max":
                final_val = max(vals) if vals else 0
            elif agg_type == "latest":
                # Get the value of the record with the most recent timestamp
                sorted_data = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
                final_val = sorted_data[0].get("value", 0)
            else: # avg
                final_val = sum(vals) / len(vals) if vals else 0

            # Use the latest record as the base for metadata, but override the value
            latest_record = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
            latest_record["value"] = round(float(final_val), 2)
            latest_record["sample_count"] = len(data)
            latest_record["agg_used"] = agg_type
            actuals.append(latest_record)

        table = Table(title=f"Breach Report: {contract_id}", show_lines=True)
        table.add_column("KPI", style="cyan")
        table.add_column("Target", style="dim")
        table.add_column("Actual", style="white")
        table.add_column("Status", justify="center")
        table.add_column("Penalty Triggered", style="yellow")
        table.add_column("Required Remediation", style="magenta")

        breaches_found = 0
        for actual in actuals:
            kpi = kpi_map.get(normalize_id(actual["kpi_id"]))
            if not kpi: continue

            result = BreachEngine.check_breach(kpi, actual, sample_count=actual.get("sample_count", 1))

            # Always insert the breach result so the UI can show "OK" statuses and latest actuals
            await MongoDB.insert_breach(result.model_dump())

            status = "[green]ON TRACK[/green]"
            remediation_info = "-"
            if result.is_breach:
                status = "[red]BREACH[/red]"
                breaches_found += 1

                # Get remediation from kpi vault
                rem = kpi.get("remediation")
                sla = kpi.get("remediation_sla")
                if rem:
                    remediation_info = f"{rem}"
                    if sla:
                        remediation_info += f" [dim](SLA: {sla})[/dim]"

            table.add_row(
                kpi["name"],
                f"{kpi['operator']} {kpi['value_min']} {kpi['unit']}",
                f"{actual['value']} {actual['unit']} [dim]({actual['agg_used']} of {actual['sample_count']})[/dim]",
                status,
                f"[bold red]${result.penalty_amount:,.2f}[/bold red]" if result.is_breach else "-",
                remediation_info
            )


        console.print(table)
        if breaches_found > 0:
            console.print(f"[bold red]⚠ {breaches_found} breach(es) detected![/bold red]")
        else:
            console.print("[bold green]✅ All KPIs are currently on track.[/bold green]")

    asyncio.run(_run())


@cli.command()
@click.argument("contract_id")
def list_kpis(contract_id: str):
    """List all saved KPIs in the vault."""
    async def _run():
        await MongoDB.connect()
        kpis = await MongoDB.get_kpis(contract_id)
        if not kpis:
            console.print("[yellow]No KPIs found.[/yellow]")
            return

        table = Table(title="KPI Vault")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Threshold", style="yellow")

        for kpi in kpis:
            table.add_row(kpi["kpi_id"], kpi["name"], f"{kpi['operator']} {kpi['value_min']} {kpi['unit']}")
        console.print(table)
    asyncio.run(_run())


@cli.command()
@click.argument("contract_id")
@click.option("--file", "-f", help="Path to CSV or JSON file")
@click.option("--kpi-id", help="Direct mapping to a KPI ID")
@click.option("--value", type=float, help="Numeric value for the actual")
@click.option("--unit", help="Unit of measurement")
@click.option("--source", default="structured", help="Source of the data (e.g., api, erp, csv)")
def ingest_actuals(contract_id: str, file: str | None = None, kpi_id: str | None = None, value: float | None = None, unit: str | None = None, source: str = "structured"):
    """Ingest structured performance data (CSV/JSON or single values)."""
    from app.db.models import OperationalActual

    async def _run():
        await MongoDB.connect()
        actuals_to_insert = []

        # Get existing KPIs for validation/mapping
        kpis = await MongoDB.get_kpis(contract_id)
        kpi_ids = {k["kpi_id"] for k in kpis}
        # Map common patterns like "KPI-6" to the internal ID
        pattern_map = {}
        for k in kpis:
            name = k.get("name", "")
            # Try to extract "KPI-N" from name
            import re
            match = re.search(r"KPI-?(\d+)", name, re.I)
            if match:
                num = match.group(1)
                pattern_map[f"kpi_{num}"] = k["kpi_id"]
                pattern_map[f"kpi_{int(num):03d}"] = k["kpi_id"]
                pattern_map[f"kpi_{num}_target"] = k["kpi_id"]
                pattern_map[f"kpi_{int(num):03d}_target"] = k["kpi_id"]

        if file:
            path = Path(file)
            if not path.exists():
                console.print(f"[red]File not found: {file}[/red]")
                return

            try:
                if path.suffix == ".csv":
                    with open(path, "r") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            raw_id = row["kpi_id"]
                            # Try mapping
                            target_id = raw_id
                            if raw_id not in kpi_ids:
                                # Try pattern map (e.g. kpi_006_hot -> remove _hot suffix)
                                base_id = re.sub(r"_[a-z]+$", "", raw_id.lower())
                                if base_id in pattern_map:
                                    target_id = pattern_map[base_id]
                                elif raw_id.lower() in pattern_map:
                                    target_id = pattern_map[raw_id.lower()]
                                else:
                                    # Try to find number in raw_id
                                    num_match = re.search(r"(\d+)", raw_id)
                                    if num_match:
                                        num = num_match.group(1)
                                        if f"kpi_{num}" in pattern_map:
                                            target_id = pattern_map[f"kpi_{num}"]

                            if target_id not in kpi_ids:
                                console.print(f"[yellow]Warning: KPI ID '{raw_id}' not found in vault. Ingesting as-is.[/yellow]")

                            actuals_to_insert.append(OperationalActual(
                                contract_id=contract_id,
                                kpi_id=target_id,
                                value=float(row["value"].replace("%", "").strip()) if isinstance(row["value"], str) else row["value"],
                                unit=row.get("unit", ""),
                                timestamp=row.get("timestamp") or datetime.now().isoformat(),
                                source=row.get("source") or source,
                                metadata={"filename": path.name, "original_id": raw_id}
                            ))
                elif path.suffix == ".json":
                    with open(path, "r") as f:
                        data = json.load(f)
                        # Use builtins.list if shadowed, but rename should fix it
                        if isinstance(data, (list, tuple)):
                            items = data
                        else:
                            items = [data]

                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            item["contract_id"] = contract_id
                            item.pop("actual_id", None)
                            actuals_to_insert.append(OperationalActual(**item))
            except Exception as e:
                console.print(f"[red]Error parsing file: {e}[/red]")
                return

        elif kpi_id and value is not None:
            actuals_to_insert.append(OperationalActual(
                contract_id=contract_id,
                kpi_id=kpi_id,
                value=value,
                unit=unit or "",
                source=source
            ))

        if not actuals_to_insert:
            console.print("[yellow]No data provided to ingest. Use --file or --kpi-id/--value.[/yellow]")
            return

        for actual in actuals_to_insert:
            await MongoDB.insert_actual(actual.model_dump())

        console.print(f"[green]✓ Successfully ingested {len(actuals_to_insert)} actual(s).[/green]")

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
