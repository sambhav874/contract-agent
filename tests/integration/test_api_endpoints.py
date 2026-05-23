import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime

from app.api import app

@pytest.fixture
def client():
    with patch("app.api.MongoDB") as mock_mongo:
        # Define default dummy return values
        mock_mongo.list_contracts = AsyncMock(return_value=[{"_id": "123", "contract_id": "test-contract-1", "parties": [{"role": "supplier", "name": "Vendor A"}]}])
        mock_mongo.get_contract = AsyncMock(return_value={"_id": "123", "contract_id": "test-contract-1", "name": "Test", "currency": "USD"})
        mock_mongo.get_kpis = AsyncMock(return_value=[{"_id": "123", "kpi_id": "kpi-1", "name": "KPI 1", "value_min": 10, "operator": ">=", "aggregation_type": "avg"}])
        mock_mongo.get_breaches = AsyncMock(return_value=[{"_id": "123", "breach_id": "b-1", "kpi_id": "kpi-1", "contract_id": "test-contract-1", "is_breach": True, "penalty_amount": 50.0}])
        mock_mongo.get_all_actuals = AsyncMock(return_value=[{"_id": "123", "kpi_id": "kpi-1", "value": 100, "timestamp": "2026-01-01T00:00:00"}])
        mock_mongo.update_breach = AsyncMock(return_value=True)
        mock_mongo.insert_contract = AsyncMock()
        mock_mongo.insert_chunks = AsyncMock()
        mock_mongo.insert_actual = AsyncMock()
        mock_mongo.insert_raw_actual = AsyncMock()
        mock_mongo.upsert_mapping_rule = AsyncMock()
        mock_mongo.save_qa_categories = AsyncMock()
        mock_mongo.save_qa_pair = AsyncMock()
        mock_mongo.get_saved_qa = AsyncMock(return_value=[{"_id": "123", "qa_id": "qa-1"}])
        mock_mongo.delete_saved_qa = AsyncMock(return_value=True)
        mock_mongo.get_qa_categories = AsyncMock(return_value=[{"_id": "123", "category": "Legal"}])
        mock_mongo.upsert_kpis = AsyncMock()

        # mock collection for generate-email
        mock_coll = AsyncMock()
        mock_coll.find_one = AsyncMock(return_value={"contract_id": "test-contract-1", "kpi_id": "kpi-1", "is_breach": True, "penalty_amount": 50.0, "actual_value": 5.0})
        mock_mongo.get_collection.return_value = mock_coll

        yield TestClient(app)

def test_list_contracts(client):
    response = client.get("/contracts")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_contract(client):
    response = client.get("/contracts/test-contract-1")
    assert response.status_code == 200
    assert response.json()["name"] == "Test"

def test_get_kpis(client):
    response = client.get("/contracts/test-contract-1/kpis")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_breaches(client):
    response = client.get("/contracts/test-contract-1/breaches")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_performance(client):
    response = client.get("/contracts/test-contract-1/performance")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_update_breach(client):
    response = client.put("/breaches/b-1", json={"status": "resolved"})
    assert response.status_code == 200
    assert "status" in response.json()["updated_fields"]

def test_portfolio_summary(client):
    response = client.get("/portfolio/summary")
    assert response.status_code == 200
    assert "summary" in response.json()
    assert response.json()["summary"]["total_contracts"] == 1

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@patch("app.api.run_evaluation")
def test_evaluate_contract(mock_run, client):
    mock_run.return_value = [{"_id": "123", "is_breach": True}]
    response = client.post("/contracts/test-contract-1/evaluate")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

@patch("app.api.ChatAgent")
def test_chat_with_contract(mock_agent_class, client):
    mock_agent = MagicMock()
    async def mock_stream(*args, **kwargs):
        yield {"text": "hello"}
    mock_agent.answer_question_stream = mock_stream
    mock_agent_class.return_value = mock_agent

    response = client.post("/contracts/test-contract-1/chat", json={"question": "what is this?"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

@patch("app.api.clear_session")
def test_clear_chat_session(mock_clear, client):
    response = client.delete("/chat-session/session-123")
    assert response.status_code == 200
    assert response.json()["status"] == "cleared"

def test_upload_contract(client):
    with patch("os.makedirs"), patch("builtins.open") as mock_open:
        mock_file = {"file": ("test.md", b"some content", "text/markdown")}
        response = client.post("/contracts/upload", files=mock_file)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

def test_list_available_contracts(client):
    with patch("os.path.exists", return_value=True), patch("os.listdir", return_value=["test.md"]), patch("os.stat") as mock_stat:
        mock_s = MagicMock()
        mock_s.st_size = 100
        mock_s.st_mtime = 1715694200
        mock_stat.return_value = mock_s
        response = client.get("/available-contracts")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["filename"] == "test.md"

@patch("app.api.parse_contract")
@patch("app.api.hierarchical_chunk")
@patch("app.api.get_embedding_service")
def test_ingest_contract(mock_embed_service, mock_chunk, mock_parse, client):
    mock_metadata = MagicMock()
    mock_metadata.contract_id = "test-contract-1"
    mock_metadata.name = "test.md"
    mock_parse.return_value = (mock_metadata, {}, "some text content")
    mock_chunk.return_value = []

    mock_embed = AsyncMock()
    mock_embed.embed_chunks = AsyncMock(return_value=[])
    mock_embed_service.return_value = mock_embed

    with patch("os.path.exists", return_value=True):
        response = client.post("/contracts/ingest", json={"filename": "test.md"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"

@patch("app.api.KPIAgent")
@patch("app.api.route_intent")
def test_extract_kpis(mock_route, mock_kpi_agent_class, client):
    mock_route.return_value = MagicMock()
    mock_agent = AsyncMock()
    mock_res = MagicMock()
    mock_res.kpis = [MagicMock()]
    mock_agent.analyze = AsyncMock(return_value=mock_res)
    mock_kpi_agent_class.return_value = mock_agent

    response = client.post("/contracts/test-contract-1/extract-kpis")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_ingest_actuals(client):
    response = client.post("/contracts/test-contract-1/actuals", json={"actuals": [{"kpi_id": "kpi-1", "value": 20, "unit": "USD"}]})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_upload_actuals_csv(client):
    csv_data = b"kpi_id,value,unit\nkpi-1,25,hours\n"
    response = client.post("/contracts/test-contract-1/actuals/upload", files={"file": ("actuals.csv", csv_data, "text/csv")})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_ingest_raw_actuals(client):
    response = client.post("/contracts/test-contract-1/raw-actuals", json={"data": {"foo": "bar"}})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_create_mapping_rule(client):
    response = client.post("/contracts/test-contract-1/mappings", json={"source_match": "s1", "kpi_id": "kpi-1"})
    assert response.status_code == 200
    assert "rule_id" in response.json()

@patch("app.api.ETLProcessor")
def test_run_etl(mock_etl, client):
    mock_etl.process_contract_actuals = AsyncMock(return_value={"processed": 1})
    response = client.post("/contracts/test-contract-1/run-etl")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

def test_get_kpi_timeseries(client):
    response = client.get("/contracts/test-contract-1/kpis/kpi-1/timeseries")
    assert response.status_code == 200
    assert "kpi" in response.json()

def test_generate_breach_email(client):
    response = client.post("/breaches/b-1/generate-email")
    assert response.status_code == 200
    assert "subject" in response.json()

def test_send_breach_email(client):
    response = client.post("/breaches/b-1/send-email", json={"to": "test@example.com", "subject": "alert", "body": "text"})
    assert response.status_code == 200
    assert response.json()["status"] == "sent"

@patch("app.api._generate_qa_categories")
def test_get_qa_categories(mock_gen, client):
    # If categories are returned from MongoDB
    response = client.get("/contracts/test-contract-1/qa/categories")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

@patch("app.api.call_gemini")
@patch("app.api.get_retriever")
def test_generate_qa_categories_endpoint(mock_retriever_fn, mock_call_gemini, client):
    mock_ret = AsyncMock()
    mock_ret.fetch = AsyncMock(return_value=[])
    mock_retriever_fn.return_value = mock_ret
    mock_call_gemini.return_value = [{"category": "Compliance", "description": "desc", "questions": ["q1"]}]

    response = client.post("/contracts/test-contract-1/qa/generate")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

@patch("app.api.ChatAgent")
def test_search_qa_answer(mock_agent_class, client):
    mock_agent = MagicMock()
    mock_ret = AsyncMock()
    mock_ret.fetch = AsyncMock(return_value=[{"structural_path": "path", "text": "snippet"}])
    mock_agent.retriever = mock_ret
    mock_agent_class.return_value = mock_agent

    response = client.post("/contracts/test-contract-1/qa/search", json={"question": "is this fine?"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_save_qa_pair(client):
    response = client.post("/contracts/test-contract-1/qa/save", json={"question": "q", "answer": "a"})
    assert response.status_code == 200
    assert "qa_id" in response.json()

def test_get_saved_qa(client):
    response = client.get("/contracts/test-contract-1/qa/saved")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_delete_saved_qa(client):
    response = client.delete("/contracts/test-contract-1/qa/saved/qa-1")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

@patch("app.api.ChatAgent")
def test_orchestrate_contract(mock_agent_class, client):
    mock_agent = AsyncMock()
    mock_agent.answer_question = AsyncMock(return_value="done")
    mock_agent_class.return_value = mock_agent

    response = client.post("/contracts/test-contract-1/orchestrate", json={"goal": "verify"})
    assert response.status_code == 200
    assert response.json()["result"] == "done"

def test_health_observability(client):
    with patch("app.api.ChatAgent") as mock_agent_class:
        mock_agent = MagicMock()
        mock_agent.safety.get_status.return_value = {"status": "ok"}
        mock_agent_class.return_value = mock_agent

        response = client.get("/health/observability")
        assert response.status_code == 200
        assert "safety" in response.json()
