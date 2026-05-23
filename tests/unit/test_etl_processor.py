import pytest
from unittest.mock import AsyncMock, patch
from app.ingestion.etl_processor import ETLProcessor, get_by_path

def test_get_by_path():
    data = {"a": {"b": {"c": 123}}}
    assert get_by_path(data, "a.b.c") == 123
    assert get_by_path(data, "a.x") is None

@pytest.mark.asyncio
async def test_process_contract_actuals():
    with patch("app.ingestion.etl_processor.MongoDB") as mock_mongo:
        # Mock pending records
        mock_mongo.get_pending_raw_actuals = AsyncMock(return_value=[
            {"raw_id": "r1", "source": "systemA", "data": {"val": 100, "ts": "2024-01-01"}}
        ])
        # Mock rules
        mock_mongo.get_mapping_rules = AsyncMock(return_value=[
            {
                "rule_id": "rule1",
                "source_match": "systemA",
                "kpi_id": "k1",
                "field_mappings": {"value": "val", "timestamp": "ts"}
            }
        ])

        mock_mongo.insert_actual = AsyncMock()
        mock_mongo.update_raw_actual_status = AsyncMock()

        result = await ETLProcessor.process_contract_actuals("test-contract")

        assert result["processed"] == 1
        assert result["errors"] == 0
        assert mock_mongo.insert_actual.called
        assert mock_mongo.update_raw_actual_status.called
