import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.tasks.celery_tasks import ingest_contract, analyze_contract

def test_ingest_contract():
    with patch("app.ingestion.parser.parse_contract") as mock_parse:
        with patch("app.ingestion.chunker.hierarchical_chunk") as mock_chunk:
            with patch("app.ingestion.embedder.get_embedding_service") as mock_get_embedder:
                with patch("app.db.mongodb.MongoDB") as mock_mongo:
                    with patch("app.tasks.celery_tasks.async_to_sync") as mock_async_to_sync:

                        mock_metadata = MagicMock()
                        mock_metadata.contract_id = "test"
                        mock_parse.return_value = (mock_metadata, {}, "text")
                        mock_chunk.return_value = [{"text": "chunk1"}]

                        mock_embedder = MagicMock()
                        mock_embedder.embed_chunks.return_value = [{"text": "chunk1", "embedding": [0.1]}]
                        mock_get_embedder.return_value = mock_embedder

                        # Mock async_to_sync behavior
                        def side_effect(func):
                            if func == mock_parse:
                                return lambda *a, **k: (mock_metadata, {}, "text")
                            if func == mock_embedder.embed_chunks:
                                return lambda *a, **k: [{"text": "chunk1", "embedding": [0.1]}]
                            return lambda *a, **k: None
                        mock_async_to_sync.side_effect = side_effect

                        # Call celery task
                        ingest_contract("file.md", "test-contract")

                        assert mock_chunk.called
                        assert mock_get_embedder.called

def test_analyze_contract():
    with patch("app.db.mongodb.MongoDB") as mock_mongo:
        with patch("app.routing.intent_router.route_intent") as mock_route:
            with patch("app.agents.risk_agent.RiskAgent") as mock_agent_cls:
                with patch("app.synthesis.synthesiser.synthesise_output") as mock_synth:
                    with patch("app.tasks.celery_tasks.async_to_sync") as mock_async_to_sync:

                        mock_agent = MagicMock()
                        mock_agent_cls.return_value = mock_agent

                        def side_effect(func):
                            if func == mock_mongo.get_contract:
                                return lambda *a, **k: {"contract_id": "test"}
                            if func == mock_route:
                                return lambda *a, **k: MagicMock()
                            if func == mock_agent.analyze:
                                return lambda *a, **k: MagicMock()
                            if func == mock_synth:
                                return lambda *a, **k: {"result": "test"}
                            return lambda *a, **k: None

                        mock_async_to_sync.side_effect = side_effect

                        result = analyze_contract("test", "risk", "query")
                        assert result == {"result": "test"}
