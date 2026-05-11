from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime

from app.db.mongodb import MongoDB
from app.config import settings
from app.agents.breach_engine import BreachEngine
from app.agents.chat_agent import ChatAgent

app = FastAPI(title="Contract Guardian API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_client():
    await MongoDB.connect()

@app.on_event("shutdown")
async def shutdown_db_client():
    await MongoDB.disconnect()

@app.get("/contracts")
async def list_contracts():
    contracts = await MongoDB.list_contracts()
    # Convert ObjectId to string for JSON serialization
    for c in contracts:
        if "_id" in c:
            c["_id"] = str(c["_id"])
    return contracts

@app.get("/contracts/{contract_id}")
async def get_contract(contract_id: str):
    contract = await MongoDB.get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if "_id" in contract:
        contract["_id"] = str(contract["_id"])
    return contract

@app.get("/contracts/{contract_id}/kpis")
async def get_kpis(contract_id: str):
    kpis = await MongoDB.get_kpis(contract_id)
    for k in kpis:
        if "_id" in k:
            k["_id"] = str(k["_id"])
    return kpis

@app.get("/contracts/{contract_id}/breaches")
async def get_breaches(contract_id: str):
    breaches = await MongoDB.get_breaches(contract_id)
    for b in breaches:
        if "_id" in b:
            b["_id"] = str(b["_id"])
    return breaches

@app.get("/contracts/{contract_id}/performance")
async def get_performance(contract_id: str):
    actuals = await MongoDB.get_all_actuals(contract_id)
    for a in actuals:
        if "_id" in a:
            a["_id"] = str(a["_id"])
    return actuals

@app.post("/contracts/{contract_id}/evaluate")
async def evaluate_contract(contract_id: str):
    """Run breach evaluation: seed actuals, compare against KPIs, persist flags."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.check_breaches import run_evaluation

    results = await run_evaluation(contract_id)
    # Clean ObjectIds for JSON
    clean = []
    for r in results:
        if "_id" in r:
            r["_id"] = str(r["_id"])
        clean.append(r)
    return {"status": "completed", "flags_count": len(clean), "breaches": sum(1 for r in clean if r.get("is_breach")), "flags": clean}
    
@app.put("/breaches/{breach_id}")
async def update_breach(breach_id: str, updates: Dict[str, Any]):
    """Update breach status or notes."""
    allowed_fields = ["status", "notes", "remediation", "remediation_sla"]
    filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
    
    if not filtered_updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
        
    success = await MongoDB.update_breach(breach_id, filtered_updates)
    if not success:
        raise HTTPException(status_code=404, detail="Breach not found")
        
    return {"status": "success", "updated_fields": list(filtered_updates.keys())}

@app.post("/contracts/{contract_id}/chat")
async def chat_with_contract(contract_id: str, payload: dict):
    question = payload.get("question")
    breach_id = payload.get("breach_id")
    include_data = payload.get("include_data_context", True)
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    # Pre-fetch structured data so the agent doesn't re-query
    kpis, breaches, actuals = [], [], []
    if include_data:
        kpis = await MongoDB.get_kpis(contract_id)
        breaches = await MongoDB.get_breaches(contract_id)
        actuals = await MongoDB.get_all_actuals(contract_id)
        # Clean ObjectIds for serialization
        for k in kpis:
            if "_id" in k: k["_id"] = str(k["_id"])
        for b in breaches:
            if "_id" in b: b["_id"] = str(b["_id"])
        for a in actuals:
            if "_id" in a: a["_id"] = str(a["_id"])
    
    agent = ChatAgent(contract_id)
    response = await agent.answer_question(
        question,
        context_breach_id=breach_id,
        kpis=kpis,
        breaches=breaches,
        actuals=actuals,
    )
    return response

@app.get("/available-contracts")
async def list_available_contracts():
    """List local .md and .pdf files available for ingestion."""
    import os
    fixtures_dir = os.path.join(os.getcwd(), "tests", "fixtures")
    if not os.path.exists(fixtures_dir):
        return []
    
    files = []
    for f in os.listdir(fixtures_dir):
        if f.endswith(".md") or f.endswith(".pdf"):
            stats = os.stat(os.path.join(fixtures_dir, f))
            files.append({
                "filename": f,
                "path": os.path.join("tests", "fixtures", f),
                "size": stats.st_size,
                "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
            })
    return files

@app.post("/contracts/ingest")
async def ingest_contract(payload: dict):
    """Ingest a local file into MongoDB."""
    from app.ingestion.parser import parse_contract
    from app.ingestion.chunker import hierarchical_chunk
    from app.ingestion.embedder import get_embedding_service
    import os
    
    filename = payload.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    file_path = os.path.join(os.getcwd(), "tests", "fixtures", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    # 1. Parse
    contract_metadata, structural_map = await parse_contract(file_path, name=filename)
    
    # 2. Read text and chunk
    with open(file_path, "r") as f:
        text = f.read()
    chunks = hierarchical_chunk(text, contract_metadata.contract_id, structural_map)
    
    # 3. Embed
    embedder = get_embedding_service()
    embedded_chunks = await embedder.embed_chunks(chunks)
    
    # 4. Save
    await MongoDB.insert_contract(contract_metadata)
    await MongoDB.insert_chunks(embedded_chunks)
    
    return {
        "status": "success",
        "contract_id": contract_metadata.contract_id,
        "name": contract_metadata.name,
        "chunks_count": len(chunks)
    }

@app.post("/contracts/{contract_id}/extract-kpis")
async def extract_kpis(contract_id: str):
    """Run agentic KPI extraction and save results."""
    from app.agents.kpi_agent import KPIAgent
    from app.routing.intent_router import route_intent
    from app.db.models import StructuralMap
    
    # Get metadata for structural map
    metadata = await MongoDB.get_contract(contract_id)
    s_map = None
    if metadata and metadata.get("structural_map"):
        s_map = StructuralMap(**metadata["structural_map"])
    
    # Route intent to get a proper structural-map-aware plan
    plan = await route_intent("kpi", structural_map=s_map)
    
    agent = KPIAgent()
    result = await agent.analyze(plan, contract_id, "")
    
    # Save to DB
    kpis_data = [k.model_dump() for k in result.kpis]
    await MongoDB.upsert_kpis(contract_id, kpis_data)
    
    return {
        "status": "success",
        "kpis_count": len(kpis_data),
        "kpis": kpis_data
    }

@app.post("/contracts/{contract_id}/actuals")
async def ingest_actuals(contract_id: str, payload: Dict[str, Any]):
    """Ingest performance actuals via JSON."""
    from app.db.models import OperationalActual
    from uuid import uuid4
    
    # Handle single or list
    data_list = payload.get("actuals") if "actuals" in payload else [payload]
    
    results = []
    for item in data_list:
        actual = OperationalActual(
            actual_id=str(uuid4()),
            contract_id=contract_id,
            kpi_id=item.get("kpi_id"),
            value=float(item.get("value", 0)),
            unit=item.get("unit"),
            timestamp=item.get("timestamp") or datetime.now().isoformat(),
            source=item.get("source", "api"),
            metadata=item.get("metadata", {})
        )
        await MongoDB.insert_actual(actual.model_dump())
        results.append(actual.model_dump())
        
    return {"status": "success", "count": len(results), "actuals": results}

@app.post("/contracts/{contract_id}/actuals/upload")
async def upload_actuals_csv(contract_id: str, file: UploadFile = File(...)):
    """Upload and parse a CSV file of performance actuals."""
    import csv
    import io
    from app.db.models import OperationalActual
    from uuid import uuid4
    
    content = await file.read()
    stream = io.StringIO(content.decode("utf-8"))
    reader = csv.DictReader(stream)
    
    results = []
    for row in reader:
        # Support 'timestamp' column if present, else use now
        ts = row.get("timestamp") or datetime.now().isoformat()
        
        actual = OperationalActual(
            actual_id=str(uuid4()),
            contract_id=contract_id,
            kpi_id=row.get("kpi_id"),
            value=float(row.get("value", 0)),
            unit=row.get("unit"),
            timestamp=ts,
            source=f"upload:{file.filename}",
            metadata={"filename": file.filename}
        )
        await MongoDB.insert_actual(actual.model_dump())
        results.append(actual.model_dump())
        
    return {"status": "success", "count": len(results), "filename": file.filename}


# ── Per-KPI Time-Series ──────────────────────────────────────────────

@app.get("/contracts/{contract_id}/kpis/{kpi_id}/timeseries")
async def get_kpi_timeseries(contract_id: str, kpi_id: str):
    """Get time-series actuals for a specific KPI with stats and trend."""
    # Normalize IDs for matching
    def norm(idx): return str(idx).lower().replace("-", "_")
    target = norm(kpi_id)
    
    # Fetch KPI metadata
    kpis = await MongoDB.get_kpis(contract_id)
    kpi = next((k for k in kpis if norm(k.get("kpi_id", "")) == target), None)
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")
    
    # Fetch all actuals for this contract and filter by kpi_id
    all_actuals = await MongoDB.get_all_actuals(contract_id)
    actuals = [a for a in all_actuals if norm(a.get("kpi_id", "")) == target]
    
    # Sort by timestamp ascending for charting
    actuals.sort(key=lambda a: a.get("timestamp", ""))
    
    # Clean ObjectIds
    for a in actuals:
        if "_id" in a: a["_id"] = str(a["_id"])
    if "_id" in kpi: kpi["_id"] = str(kpi["_id"])
    
    # Compute stats
    values = [float(a.get("value", 0)) for a in actuals if a.get("value") is not None]
    threshold = kpi.get("value_min", 0)
    op = kpi.get("operator", ">=")
    
    stats = {}
    if values:
        stats["min"] = round(min(values), 2)
        stats["max"] = round(max(values), 2)
        stats["avg"] = round(sum(values) / len(values), 2)
        stats["count"] = len(values)
        
        # Compliance rate
        if op == ">=":
            compliant = sum(1 for v in values if v >= threshold)
        elif op == "<=":
            compliant = sum(1 for v in values if v <= threshold)
        elif op == "==":
            compliant = sum(1 for v in values if v == threshold)
        else:
            compliant = len(values)
        stats["compliance_rate"] = round((compliant / len(values)) * 100, 1) if values else 0
        
        # Trend direction: compare avg of last 5 vs previous 5
        if len(values) >= 4:
            mid = len(values) // 2
            recent_avg = sum(values[mid:]) / len(values[mid:])
            older_avg = sum(values[:mid]) / len(values[:mid])
            delta = recent_avg - older_avg
            # For <= operators, improving means going DOWN
            if op == "<=":
                delta = -delta
            if delta > 0.5:
                stats["trend"] = "improving"
            elif delta < -0.5:
                stats["trend"] = "declining"
            else:
                stats["trend"] = "stable"
        else:
            stats["trend"] = "insufficient_data"
    
    # Fetch breaches for this KPI
    all_breaches = await MongoDB.get_breaches(contract_id)
    kpi_breaches = [b for b in all_breaches if norm(b.get("kpi_id", "")) == target]
    for b in kpi_breaches:
        if "_id" in b: b["_id"] = str(b["_id"])
    
    # Build response for frontend
    # Note: Frontend expects { data: [], stats: {}, trend: { threshold, direction } }
    return {
        "kpi": kpi,
        "data": actuals,  # Frontend calls it 'data'
        "stats": stats,
        "breaches": kpi_breaches,
        "trend": {
            "direction": stats.get("trend"),
            "threshold": threshold
        }
    }


# ── Breach Email Generation ──────────────────────────────────────────

@app.post("/breaches/{breach_id}/generate-email")
async def generate_breach_email(breach_id: str):
    """Generate a remediation email for a breach using stored KPI email template."""
    from bson import ObjectId
    
    breaches_coll = MongoDB.get_collection("breaches")
    breach = await breaches_coll.find_one({"breach_id": breach_id})
    if not breach:
        try:
            breach = await breaches_coll.find_one({"_id": ObjectId(breach_id)})
        except:
            pass
    if not breach:
        raise HTTPException(status_code=404, detail="Breach not found")
    
    # Get the KPI for template and metadata
    def norm(idx): return str(idx).lower().replace("-", "_")
    kpis = await MongoDB.get_kpis(breach["contract_id"])
    kpi = next((k for k in kpis if norm(k.get("kpi_id", "")) == norm(breach.get("kpi_id", ""))), None)
    
    # Get contract name
    contract = await MongoDB.get_contract(breach["contract_id"])
    contract_name = contract.get("name", breach["contract_id"]) if contract else breach["contract_id"]
    
    # Build email from KPI's stored template or generate a default
    kpi_name = kpi.get("name", breach.get("kpi_id", "Unknown KPI")) if kpi else breach.get("kpi_id", "Unknown KPI")
    template = (kpi.get("breach_email_template") or "") if kpi else ""
    
    if template:
        # Fill template placeholders
        body = template
        body = body.replace("{{kpi_name}}", kpi_name)
        body = body.replace("{{threshold}}", f"{kpi.get('operator', '')} {kpi.get('value_min', '')} {kpi.get('unit', '')}")
        body = body.replace("{{actual_value}}", str(breach.get("actual_value", "")))
        body = body.replace("{{unit}}", kpi.get("unit", "") if kpi else "")
        body = body.replace("{{penalty_amount}}", f"${breach.get('penalty_amount', 0):,.2f}")
        body = body.replace("{{remediation}}", kpi.get("remediation", "Immediate corrective action required") if kpi else "Immediate corrective action required")
        body = body.replace("{{remediation_sla}}", kpi.get("remediation_sla", "As soon as possible") if kpi else "As soon as possible")
        body = body.replace("{{contract_name}}", contract_name)
    else:
        # Default template when no pre-extracted template exists
        remediation = kpi.get("remediation", "Immediate corrective action required") if kpi else "Immediate corrective action required"
        sla = kpi.get("remediation_sla", "As soon as possible") if kpi else "As soon as possible"
        penalty = breach.get("penalty_amount", 0)
        
        body = f"""Dear Team,

This is to formally notify you of a compliance breach detected under the contract "{contract_name}".

BREACH DETAILS:
- KPI: {kpi_name}
- Contractual Threshold: {kpi.get('operator', '>=')} {kpi.get('value_min', 'N/A')} {kpi.get('unit', '')}
- Actual Performance: {breach.get('actual_value', 'N/A')} {kpi.get('unit', '') if kpi else ''}
- Penalty Exposure: ${penalty:,.2f}

REQUIRED ACTION:
{remediation}

RESPONSE DEADLINE:
{sla}

Please acknowledge receipt of this notice and provide a corrective action plan within the specified SLA window.

Regards,
Contract Compliance Team"""

    subject = f"[BREACH ALERT] {kpi_name} — {contract_name}"
    
    # Suggest recipient from contract parties
    suggested_to = ""
    if contract and contract.get("parties"):
        for party in contract["parties"]:
            if party.get("role", "").lower() in ["supplier", "vendor", "contractor", "provider"]:
                suggested_to = party.get("email", party.get("name", ""))
                break
    
    return {
        "subject": subject,
        "body": body,
        "suggested_to": suggested_to,
        "breach_id": breach_id,
        "kpi_name": kpi_name,
    }


@app.post("/breaches/{breach_id}/send-email")
async def send_breach_email(breach_id: str, payload: dict):
    """Stub endpoint for sending breach notification emails.
    
    In production, this would use SMTP/SendGrid/Resend to actually send.
    For now, it logs the email and returns success.
    """
    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    
    if not to or not subject or not body:
        raise HTTPException(status_code=400, detail="to, subject, and body are required")
    
    # TODO: Implement actual email sending via SMTP
    # import smtplib
    # from email.mime.text import MIMEText
    # ...
    
    # For now, log and return success
    import logging
    logging.info(f"[EMAIL STUB] To: {to} | Subject: {subject} | Body length: {len(body)}")
    
    return {
        "status": "sent",
        "message": f"Email notification queued for {to}",
        "note": "Email sending is currently in stub mode. Configure SMTP to enable delivery."
    }


# ── Portfolio Summary ─────────────────────────────────────────────────

@app.get("/portfolio/summary")
async def portfolio_summary():
    """Aggregate compliance health across all contracts. Pure computation, no AI."""
    contracts = await MongoDB.list_contracts()
    
    portfolio = []
    for contract in contracts:
        cid = contract.get("contract_id")
        if "_id" in contract: contract["_id"] = str(contract["_id"])
        
        # Fetch data for each contract
        kpis = await MongoDB.get_kpis(cid)
        breaches = await MongoDB.get_breaches(cid)
        actuals = await MongoDB.get_all_actuals(cid)
        
        total_kpis = len(kpis)
        active_breaches = [b for b in breaches if b.get("is_breach")]
        total_breaches = len(active_breaches)
        total_penalty = sum(b.get("penalty_amount", 0) for b in active_breaches)
        
        # Compliance health: % of KPIs that are NOT breached
        evaluated_kpis = len(set(b.get("kpi_id") for b in breaches))
        on_track = len([b for b in breaches if not b.get("is_breach")])
        health_score = round((on_track / evaluated_kpis * 100), 1) if evaluated_kpis > 0 else 100.0
        
        # Get parties for supplier identification
        parties = contract.get("parties", [])
        supplier_name = None
        for p in parties:
            role = (p.get("role") or "").lower()
            if role in ["supplier", "vendor", "contractor", "provider", "caterer"]:
                supplier_name = p.get("name")
                break
        
        portfolio.append({
            "contract_id": cid,
            "name": contract.get("name", cid),
            "contract_type": contract.get("contract_type"),
            "effective_date": contract.get("effective_date"),
            "parties": parties,
            "supplier_name": supplier_name or (parties[1]["name"] if len(parties) > 1 else "Unknown"),
            "total_kpis": total_kpis,
            "evaluated_kpis": evaluated_kpis,
            "active_breaches": total_breaches,
            "total_penalty_exposure": round(total_penalty, 2),
            "health_score": health_score,
            "total_actuals": len(actuals),
        })
    
    # Aggregate stats
    total_contracts = len(portfolio)
    avg_health = round(sum(p["health_score"] for p in portfolio) / total_contracts, 1) if total_contracts > 0 else 0
    total_penalty_all = round(sum(p["total_penalty_exposure"] for p in portfolio), 2)
    total_breaches_all = sum(p["active_breaches"] for p in portfolio)
    
    return {
        "summary": {
            "total_contracts": total_contracts,
            "avg_health_score": avg_health,
            "total_penalty_exposure": total_penalty_all,
            "total_active_breaches": total_breaches_all,
        },
        "contracts": sorted(portfolio, key=lambda p: p["health_score"]),
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
