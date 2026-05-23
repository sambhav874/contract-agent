from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
import asyncio
import json
from datetime import datetime

from app.db.mongodb import MongoDB
from app.config import settings
from app.agents.breach_engine import BreachEngine
from app.agents.chat_agent import ChatAgent, clear_session
from scripts.check_breaches import run_evaluation
from app.ingestion.parser import parse_contract
from app.ingestion.chunker import hierarchical_chunk
from app.ingestion.embedder import get_embedding_service
from app.agents.kpi_agent import KPIAgent
from app.routing.intent_router import route_intent
from app.ingestion.etl_processor import ETLProcessor
from app.retrieval.retriever import get_retriever
from app.llm.gemini_client import call_gemini

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

@app.get("/contracts/{contract_id}/text")
async def get_contract_text(contract_id: str):
    import os
    import re
    from app.ingestion.parser import parse_contract

    contract = await MongoDB.get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    filename = contract.get("name")
    file_path = None

    # 1. Try filename on disk if valid and exists
    if filename and filename != "Unknown Contract":
        path = os.path.join(os.getcwd(), "tests", "fixtures", "contracts", filename)
        if os.path.exists(path):
            file_path = path

    # 2. Try contract_id-based names directly in tests/fixtures/contracts/
    if not file_path:
        for ext in ["", ".md"]:
            path = os.path.join(os.getcwd(), "tests", "fixtures", "contracts", f"{contract_id}{ext}")
            if os.path.exists(path):
                file_path = path
                break

    # 3. Specific mapping for known production IDs
    if not file_path and contract_id == "prod-logistics-v3":
        path = os.path.join(os.getcwd(), "tests", "fixtures", "contracts", "logistics_agreement_v3_production.md")
        if os.path.exists(path):
            file_path = path

    # 4. Fallback search by token overlap in tests/fixtures/contracts
    if not file_path:
        fixtures_dir = os.path.join(os.getcwd(), "tests", "fixtures", "contracts")
        if os.path.exists(fixtures_dir):
            try:
                files = [f for f in os.listdir(fixtures_dir) if os.path.isfile(os.path.join(fixtures_dir, f))]
                tokens = set(re.split(r"[_\-]", contract_id.lower()))
                best_match = None
                max_overlap = 0
                for f in files:
                    if not f.endswith(".md"):
                        continue
                    f_tokens = set(re.split(r"[_\-\.]", f.lower()))
                    overlap = len(tokens.intersection(f_tokens))
                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_match = f
                if best_match and max_overlap > 0:
                    file_path = os.path.join(fixtures_dir, best_match)
            except Exception:
                pass

    # If we successfully resolved the file path, try to parse it
    if file_path:
        try:
            _, _, text = await parse_contract(file_path, name=os.path.basename(file_path))
            return {"status": "success", "text": text}
        except Exception:
            # If parsing fails, fall back to chunks reconstruction
            pass

    # 5. Database Chunks reconstruction fallback
    try:
        chunks_coll = MongoDB.get_collection("chunks")
        # Fetch root chunks (macro/meso chunks that cover the whole document uniquely)
        db_chunks = await chunks_coll.find({
            "contract_id": contract_id,
            "chunk_level": {"$in": ["macro", "meso"]},
            "parent_chunk_id": None
        }).sort("char_start", 1).to_list(None)

        if not db_chunks:
            # Fallback to macro chunks
            db_chunks = await chunks_coll.find({
                "contract_id": contract_id,
                "chunk_level": "macro"
            }).sort("char_start", 1).to_list(None)

        if not db_chunks:
            # Fallback to all chunks
            db_chunks = await chunks_coll.find({
                "contract_id": contract_id
            }).sort("char_start", 1).to_list(None)

        if db_chunks:
            reconstructed_text = ""
            last_end = 0
            for chunk in db_chunks:
                start = chunk.get("char_start", 0)
                text = chunk.get("text", "")
                if start >= last_end:
                    reconstructed_text += " " * (start - last_end) + text
                    last_end = start + len(text)
                else:
                    overlap = last_end - start
                    if len(text) > overlap:
                        reconstructed_text += text[overlap:]
                        last_end = start + len(text)

            if reconstructed_text.strip():
                return {"status": "success", "text": reconstructed_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reconstruct contract text: {str(e)}")

    raise HTTPException(status_code=404, detail="Contract text and file could not be found or resolved")

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
    session_id = payload.get("session_id")   # multi-turn context key
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    agent = ChatAgent(contract_id)

    async def event_generator():
        async for chunk in agent.answer_question_stream(
            question,
            context_breach_id=breach_id,
            session_id=session_id,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.delete("/chat-session/{session_id}")
async def clear_chat_session(session_id: str):
    """Clear a chat session's history so the user can start a fresh conversation."""
    clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}

@app.post("/contracts/upload")
async def upload_contract(file: UploadFile = File(...)):
    """Upload a contract file (.md or .pdf) to the fixtures directory for ingestion."""
    import os
    filename = os.path.basename(file.filename or "")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    if not filename.lower().endswith((".md", ".pdf")):
        raise HTTPException(status_code=400, detail="Only .md and .pdf files are supported")

    fixtures_dir = os.path.join(os.getcwd(), "tests", "fixtures")
    os.makedirs(fixtures_dir, exist_ok=True)

    file_path = os.path.join(fixtures_dir, filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {"status": "success", "filename": filename}

@app.get("/available-contracts")
async def list_available_contracts():
    """List local .md and .pdf files available for ingestion."""
    import os
    fixtures_dir = os.path.join(os.getcwd(), "tests", "fixtures")
    if not os.path.exists(fixtures_dir):
        return []

    files = []
    for f in os.listdir(fixtures_dir):
        if f.lower().endswith((".md", ".pdf")):
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
    import os

    filename = os.path.basename(str(payload.get("filename") or ""))
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_path = os.path.join(os.getcwd(), "tests", "fixtures", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    # 1. Parse
    try:
        contract_metadata, structural_map, text = await parse_contract(file_path, name=filename)
    except Exception as exc:
        parser_name = "LiteParse" if filename.lower().endswith(".pdf") else "markdown parser"
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse {filename} with {parser_name}: {str(exc)}",
        ) from exc

    if not text or not text.strip():
        raise HTTPException(
            status_code=422,
            detail=f"Extracted text from {filename} is empty. The document might be image-based or unreadable."
        )

    # 2. Chunk
    try:
        chunks = hierarchical_chunk(text, contract_metadata.contract_id, structural_map)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to chunk parsed contract {filename}: {str(exc)}",
        ) from exc

    # 3. Embed
    try:
        embedder = get_embedding_service()
        embedded_chunks = await embedder.embed_chunks(chunks)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to embed parsed contract {filename}: {str(exc)}",
        ) from exc

    # 4. Save
    try:
        chunks_collection = MongoDB.get_collection("chunks")
        await chunks_collection.delete_many({"contract_id": contract_metadata.contract_id})
        await MongoDB.insert_contract(contract_metadata)
        await MongoDB.insert_chunks(embedded_chunks)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save ingested contract {filename}: {str(exc)}",
        ) from exc

    return {
        "status": "success",
        "contract_id": contract_metadata.contract_id,
        "name": contract_metadata.name,
        "chunks_count": len(chunks)
    }

@app.post("/contracts/{contract_id}/extract-kpis")
async def extract_kpis(contract_id: str):
    """Run agentic KPI extraction and save results."""
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


# ── Rule-Based ETL & Staging ──────────────────────────────────────────

@app.post("/contracts/{contract_id}/raw-actuals")
async def ingest_raw_actuals(contract_id: str, payload: Dict[str, Any]):
    """Ingest schema-agnostic raw data into staging."""
    from app.db.models import RawActual
    from uuid import uuid4

    # data can be single object or list
    raw_data = payload.get("data")
    if raw_data is None:
        data_list = [payload]
    elif isinstance(raw_data, list):
        data_list = raw_data
    else:
        data_list = [raw_data]
    source = payload.get("source", "generic_stream")

    results = []
    for item in data_list:
        raw = RawActual(
            raw_id=str(uuid4()),
            contract_id=contract_id,
            data=item,
            source=source,
            status="pending"
        )
        await MongoDB.insert_raw_actual(raw.model_dump())
        results.append(raw.raw_id)

    return {"status": "success", "ingested_count": len(results), "raw_ids": results}


@app.post("/contracts/{contract_id}/mappings")
async def create_mapping_rule(contract_id: str, payload: Dict[str, Any]):
    """Configure a deterministic mapping rule for a data source."""
    from app.db.models import MappingRule
    from uuid import uuid4

    rule = MappingRule(
        rule_id=str(uuid4()),
        contract_id=contract_id,
        source_match=payload.get("source_match"),
        kpi_id=payload.get("kpi_id"),
        field_mappings=payload.get("field_mappings", {})
    )

    await MongoDB.upsert_mapping_rule(rule.model_dump())
    return {"status": "success", "rule_id": rule.rule_id}


@app.post("/contracts/{contract_id}/run-etl")
async def run_etl_process(contract_id: str):
    """Trigger the rule-based ETL process for a contract."""
    stats = await ETLProcessor.process_contract_actuals(contract_id)
    return {"status": "completed", "stats": stats}


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
        stats["total"] = round(sum(values), 2)
        stats["avg"] = round(sum(values) / len(values), 2)
        stats["count"] = len(values)

        # Determine primary metric based on aggregation_type
        agg = kpi.get("aggregation_type", "avg")
        stats["primary_metric"] = stats["total"] if agg == "sum" else stats["avg"]
        stats["metric_label"] = "Total" if agg == "sum" else "Average"

        # Compliance rate calculation
        agg = kpi.get("aggregation_type", "avg")
        if agg == "sum":
            # For sum KPIs, compliance is binary: is total >= threshold?
            # Or percentage of progress toward goal
            if op == ">=":
                stats["compliance_rate"] = min(100.0, round((stats["total"] / threshold) * 100, 1)) if threshold > 0 else 100.0
            elif op == "<=":
                stats["compliance_rate"] = 100.0 if stats["total"] <= threshold else 0.0
            else:
                stats["compliance_rate"] = 100.0 if stats["total"] == threshold else 0.0
        else:
            # For avg/latest KPIs, compliance is percentage of compliant records
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

    # Resolve currency symbol from contract metadata
    currency_symbol = ""
    if contract:
        currency = (contract.get("currency") or "").upper()
        # Map common ISO codes to symbols; fall back to the code itself
        _CURRENCY_SYMBOLS = {"USD": "$", "EUR": "\u20ac", "GBP": "\u00a3", "INR": "\u20b9", "JPY": "\u00a5"}
        currency_symbol = _CURRENCY_SYMBOLS.get(currency, currency + " " if currency else "$")

    if template:
        # Fill template placeholders
        body = template
        body = body.replace("{{kpi_name}}", kpi_name)
        body = body.replace("{{threshold}}", f"{kpi.get('operator', '')} {kpi.get('value_min', '')} {kpi.get('unit', '')}")
        body = body.replace("{{actual_value}}", str(breach.get("actual_value", "")))
        body = body.replace("{{unit}}", kpi.get("unit", "") if kpi else "")
        body = body.replace("{{penalty_amount}}", f"{currency_symbol}{breach.get('penalty_amount', 0):,.2f}")
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
- Penalty Exposure: {currency_symbol}{penalty:,.2f}

REQUIRED ACTION:
{remediation}

RESPONSE DEADLINE:
{sla}

Please acknowledge receipt of this notice and provide a corrective action plan within the specified SLA window.

Regards,
Contract Compliance Team"""

    subject = f"[BREACH ALERT] {kpi_name} — {contract_name}"

    # Suggest recipient from KPI specific contact_email or contract parties
    suggested_to = kpi.get("contact_email") or ""
    if not suggested_to and contract and contract.get("parties"):
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


@app.get("/health/observability")
async def health_observability():
    """Return observability metrics from the safety guard and cost tracker."""
    from app.agents.chat_agent import ChatAgent
    agent = ChatAgent("__health_check__")
    return {
        "status": "healthy",
        "safety": agent.safety.get_status(),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/safety/check")
async def safety_check(payload: dict):
    """Check if a proposed action passes the safety guard."""
    from app.agents.safety import SafetyGuard
    guard = SafetyGuard(payload.get("config", {}))
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    safe, reason = guard.validate_tool_call(tool_name, tool_input)
    return {"safe": safe, "reason": reason if not safe else ""}


# ── Question / Answer Library ─────────────────────────────────────────

@app.get("/contracts/{contract_id}/qa/categories")
async def get_qa_categories(contract_id: str):
    """Get saved Q&A categories for this contract."""
    cats = await MongoDB.get_qa_categories(contract_id)
    for c in cats:
        if "_id" in c:
            c["_id"] = str(c["_id"])
    if not cats:
        # Auto-generate if none exist
        return await _generate_qa_categories(contract_id)
    return {"status": "success", "categories": cats}


@app.post("/contracts/{contract_id}/qa/generate")
async def generate_qa_categories(contract_id: str):
    """Regenerate Q&A categories for this contract."""
    return await _generate_qa_categories(contract_id)


async def _generate_qa_categories(contract_id: str):
    """Generate Q&A categories using Gemini and contract context."""
    retriever = get_retriever()
    contract = await MongoDB.get_contract(contract_id) or {}

    # Fetch macro-level context for category generation
    macro_chunks = await retriever.fetch(
        contract_id=contract_id,
        query="contract overview parties scope key terms KPIs obligations penalties",
        levels=["macro"],
        top_k=15
    )
    context = "\n".join(c.get("text", "")[:600] for c in macro_chunks[:5])

    system_prompt = """You are a contract analysis assistant. Given a contract overview, generate relevant categories of questions that a stakeholder might ask about this contract.
Each category should represent a domain of concern (e.g., Compliance, Financial, Legal, Operational, Technical)."""

    user_message = f"""CONTRACT CONTEXT:
{context}

CONTRACT TYPE: {contract.get('contract_type', 'Unknown')}
PARTIES: {', '.join(p.get('name', 'Unknown') for p in contract.get('parties', []))}

Generate a JSON array of categories. Each category should have:
- "category" (string): the category name
- "description" (string): brief description of what this category covers
- "questions" (array of strings): 3-5 example questions for this category

Return ONLY a JSON array. No markdown, no code blocks."""

    try:
        result = await call_gemini(
            model=settings.gemini_fast_model,
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.2,
        )
        if isinstance(result, list):
            categories = result
        elif isinstance(result, dict) and "categories" in result:
            categories = result["categories"]
        else:
            categories = []
    except Exception as e:
        return {"status": "error", "detail": str(e), "categories": []}

    # Save generated categories
    await MongoDB.save_qa_categories(contract_id, categories)
    return {"status": "success", "categories": categories}


@app.post("/contracts/{contract_id}/qa/search")
async def search_qa_answer(payload: Dict[str, Any], contract_id: str):
    """Search for an answer to a specific question using RAG/hybrid search."""
    question = payload.get("question", "")
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    # Use chat agent to search for answer
    agent = ChatAgent(contract_id)
    chunks = await agent.retriever.fetch(
        contract_id=contract_id,
        query=question,
        top_k=10,
        levels=None
    )
    # Extract relevant text snippets
    sources = [c.get("structural_path", "") for c in chunks[:5] if c.get("structural_path")]
    texts = [c.get("text", "") for c in chunks[:5]]

    return {
        "status": "success",
        "question": question,
        "sources": sources[:5],
        "snippets": texts[:5],
    }


@app.post("/contracts/{contract_id}/qa/save")
async def save_qa_pair(contract_id: str, payload: Dict[str, Any]):
    """Save a Q&A pair to the question library."""
    from app.db.models import SavedQA
    from datetime import datetime as dt

    qa = SavedQA(
        contract_id=contract_id,
        category=payload.get("category", "General"),
        question=payload.get("question", ""),
        answer=payload.get("answer", ""),
        sources=payload.get("sources", []),
        exact_quotes=payload.get("exact_quotes", []),
        justification=payload.get("justification", ""),
        confidence=payload.get("confidence", 0.0),
        created_at=dt.utcnow(),
        updated_at=dt.utcnow(),
    )
    await MongoDB.save_qa_pair(contract_id, qa.model_dump())
    return {"status": "success", "qa_id": qa.qa_id}


@app.get("/contracts/{contract_id}/qa/saved")
async def get_saved_qa(contract_id: str):
    """List all saved Q&A pairs for this contract."""
    saved = await MongoDB.get_saved_qa(contract_id)
    for s in saved:
        if "_id" in s:
            s["_id"] = str(s["_id"])
    return {"status": "success", "count": len(saved), "items": saved}


@app.delete("/contracts/{contract_id}/qa/saved/{qa_id}")
async def delete_saved_qa(contract_id: str, qa_id: str):
    """Delete a saved Q&A pair."""
    success = await MongoDB.delete_saved_qa(qa_id)
    if not success:
        raise HTTPException(status_code=404, detail="Q&A pair not found")
    return {"status": "success", "qa_id": qa_id}


# ── Multi-Agent Orchestration ─────────────────────────────────────────

@app.post("/contracts/{contract_id}/orchestrate")
async def orchestrate_contract(contract_id: str, payload: dict):
    """Run a multi-agent orchestration for a compound goal on a contract."""
    goal = payload.get("goal", "")
    if not goal:
        raise HTTPException(status_code=400, detail="goal is required")

    try:
        agent = ChatAgent(contract_id)
        result = await agent.answer_question(goal)
        return {
            "status": "success",
            "goal": goal,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/semantic")
async def get_semantic_memory(limit: int = 50):
    """Retrieve all learned semantic memories."""
    from app.memory.semantic import SemanticMemory
    sem = SemanticMemory()
    facts = await sem.list_all(limit=limit)
    for f in facts:
        if "_id" in f:
            f["_id"] = str(f["_id"])
    return {"status": "success", "count": len(facts), "items": facts}


@app.get("/memory/episodic")
async def get_episodic_memory(limit: int = 20):
    """Retrieve recent episodic memory runs."""
    from app.memory.episodic import EpisodicMemory
    epi = EpisodicMemory()
    # Let's retrieve everything or list sessions
    episodes = await MongoDB.get_collection("episodic_memory").find().sort("timestamp", -1).to_list(length=limit)
    for e in episodes:
        if "_id" in e:
            e["_id"] = str(e["_id"])
    return {"status": "success", "count": len(episodes), "items": episodes}
