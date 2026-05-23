import pytest
from unittest.mock import AsyncMock, patch
from app.retrieval.retriever import Retriever

@pytest.mark.asyncio
async def test_retriever_fetch():
    retriever = Retriever()
    with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vs:
        with patch.object(retriever, "_keyword_search", new_callable=AsyncMock) as mock_ks:
            with patch.object(retriever, "_structural_search", new_callable=AsyncMock) as mock_ss:
                with patch.object(retriever, "_rerank_voyage", new_callable=AsyncMock) as mock_rerank:
                    # Mock return values
                    mock_vs.return_value = [{"chunk_id": "c1", "text": "test"}]
                    mock_ks.return_value = [{"chunk_id": "c2", "text": "test"}]
                    mock_ss.return_value = [{"chunk_id": "c3", "text": "test"}]
                    mock_rerank.return_value = [{"chunk_id": "c1"}, {"chunk_id": "c3"}, {"chunk_id": "c2"}]

                    with patch("app.retrieval.retriever.embed_query", new_callable=AsyncMock) as mock_embed:
                        mock_embed.return_value = [0.1, 0.2]

                        results = await retriever.fetch(
                            contract_id="test",
                            query="query",
                            tags=["Article 1", "confidentiality"],
                            levels=["macro"],
                            enable_expansion=False
                        )

                        assert len(results) == 3
                        assert mock_vs.called
                        assert mock_ks.called
                        assert mock_ss.called
                        assert mock_rerank.called

@pytest.mark.asyncio
async def test_retriever_fetch_by_ids():
    retriever = Retriever()
    with patch("app.retrieval.retriever.MongoDB.get_collection") as mock_coll:
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [{"chunk_id": "c1"}]
        mock_coll.return_value.find.return_value = mock_cursor

        results = await retriever.fetch_by_ids(["c1"])
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c1"

@pytest.mark.asyncio
async def test_retriever_fetch_by_section():
    retriever = Retriever()
    with patch("app.retrieval.retriever.MongoDB.get_collection") as mock_coll:
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [{"chunk_id": "c1"}]
        mock_coll.return_value.find.return_value = mock_cursor

        results = await retriever.fetch_by_section("test", ["tag"], ["macro"])
        assert len(results) == 1

@pytest.mark.asyncio
async def test_retriever_fetch_all_sections():
    retriever = Retriever()
    with patch("app.retrieval.retriever.MongoDB.get_collection") as mock_coll:
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [{"chunk_id": "c1"}]
        mock_coll.return_value.find.return_value = mock_cursor

        results = await retriever.fetch_all_sections("test")
        assert len(results) == 1
