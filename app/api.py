from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
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
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    agent = ChatAgent(contract_id)
    response = await agent.answer_question(question, breach_id)
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
