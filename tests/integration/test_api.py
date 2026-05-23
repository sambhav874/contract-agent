"""Integration tests for the API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

# Mock required modules before importing the app
import sys
from unittest.mock import MagicMock

# Setup mock modules
# Removed global sys.modules patching as it breaks other tests
from app.db.mongodb import MongoDB  # type: ignore


class TestAPI:
    @pytest.fixture
    def client(self):
        with patch("app.agents.chat_agent.get_retriever") as mock_retriever:
            mock_r = AsyncMock()
            mock_r.fetch.return_value = []
            mock_retriever.return_value = mock_r

            with patch("app.agents.chat_agent.MongoDB") as mock_mongo:
                mock_mongo.get_contract.return_value = {
                    "contract_id": "test-contract-1",
                    "name": "Test Contract",
                    "contract_type": "service",
                    "parties": [{"name": "Acme", "role": "supplier"}],
                    "currency": "USD",
                }
                mock_mongo.get_kpis.return_value = []
                mock_mongo.get_breaches.return_value = []
                mock_mongo.get_all_actuals.return_value = []

                from app.api import app
                yield TestClient(app)

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_safety_check(self, client):
        response = client.post("/safety/check", json={
            "tool_name": "query_db",
            "tool_input": {"query": "SELECT * FROM users"},
            "config": {
                "forbidden_patterns": [r"DROP\s+TABLE"]
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data["safe"] is True

    def test_safety_check_blocked(self, client):
        response = client.post("/safety/check", json={
            "tool_name": "query_db",
            "tool_input": {"query": "DROP TABLE users"},
            "config": {
                "forbidden_patterns": [r"DROP\s+TABLE"]
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data["safe"] is False
