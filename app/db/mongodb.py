"""MongoDB connection and operations."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import settings
from app.db.models import ChunkDocument, ContractMetadata


class MongoDB:
    """MongoDB connection manager and collection accessors."""

    _client: AsyncIOMotorClient | None = None
    _db: Any = None

    @classmethod
    async def connect(cls) -> None:
        """Establish connection to MongoDB."""
        if cls._client is None:
            cls._client = AsyncIOMotorClient(settings.mongodb_uri)
            cls._db = cls._client[settings.mongodb_db_name]

    @classmethod
    async def disconnect(cls) -> None:
        """Close MongoDB connection."""
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None

    @classmethod
    def get_collection(cls, name: str) -> AsyncIOMotorCollection:
        """Get a collection by name."""
        if cls._db is None:
            raise RuntimeError("MongoDB not connected. Call connect() first.")
        return cls._db[name]

    @classmethod
    async def create_indexes(cls) -> None:
        """Create required indexes for collections."""
        await cls.connect()
        chunks = cls.get_collection("chunks")
        jobs = cls.get_collection("analysis_jobs")

        # Compound index for chunks
        await chunks.create_index([("contract_id", 1), ("chunk_level", 1), ("section_type_tags", 1)])
        await chunks.create_index("created_at")

        # Vector search index (Atlas Vector Search — must be created via Atlas UI or Admin API)
        # The index uses the *vectorSearch* type (not legacy 'vector').
        # Pre-filter fields let $vectorSearch filter on contract_id / chunk_level / section_type_tags
        # before ANN so the candidate pool stays contract-scoped.
        try:
            indexes = await chunks.list_indexes().to_list(None)
            has_vector_index = any(
                idx.get("name") == "chunk_embedding_index" for idx in indexes
            )
            if not has_vector_index:
                import json as _json
                index_def = cls.vector_search_index_definition()
                print(
                    "\n[contract-agent] Atlas Vector Search index not found.\n"
                    "Create it in MongoDB Atlas UI:\n"
                    "  Database > Search > Create Search Index > JSON Editor\n"
                    "  Select 'Vector Search' type, target collection: chunks\n"
                    "  Paste the following definition:\n\n"
                    + _json.dumps(index_def, indent=2)
                    + "\n\nOr use the Admin API / mongocli (see scripts/create_vector_index.py)\n"
                )
        except Exception:
            pass  # Index check failed silently; Atlas may still have the index

        await jobs.create_index("status")
        await jobs.create_index("created_at")

    @classmethod
    async def insert_contract(cls, metadata: ContractMetadata) -> str:
        """Insert a contract metadata document."""
        collection = cls.get_collection("contracts")
        result = await collection.insert_one(metadata.model_dump())
        return str(result.inserted_id)

    @classmethod
    async def get_contract(cls, contract_id: str) -> dict[str, Any] | None:
        """Get a contract by ID."""
        collection = cls.get_collection("contracts")
        return await collection.find_one({"contract_id": contract_id})

    @classmethod
    async def list_contracts(cls) -> list[dict[str, Any]]:
        """List all contracts."""
        collection = cls.get_collection("contracts")
        return await collection.find({}, {"embedding": 0}).to_list(None)

    @classmethod
    async def delete_contract(cls, contract_id: str) -> None:
        """Delete a contract and all its chunks."""
        contracts = cls.get_collection("contracts")
        chunks = cls.get_collection("chunks")
        jobs = cls.get_collection("analysis_jobs")

        await contracts.delete_one({"contract_id": contract_id})
        await chunks.delete_many({"contract_id": contract_id})
        await jobs.delete_many({"contract_id": contract_id})

    @classmethod
    async def insert_chunks(cls, chunks: list[ChunkDocument]) -> list[str]:
        """Insert multiple chunk documents."""
        collection = cls.get_collection("chunks")
        docs = [chunk.model_dump() for chunk in chunks]
        result = await collection.insert_many(docs)
        return [str(id) for id in result.inserted_ids]

    @classmethod
    async def get_analysis_job(cls, job_id: str) -> dict[str, Any] | None:
        """Get an analysis job by ID."""
        collection = cls.get_collection("analysis_jobs")
        return await collection.find_one({"job_id": job_id})

    @classmethod
    async def update_analysis_job(cls, job_id: str, update: dict[str, Any]) -> None:
        """Update an analysis job."""
        collection = cls.get_collection("analysis_jobs")
        await collection.update_one({"job_id": job_id}, {"$set": update})

    @classmethod
    async def get_latest_job(cls, contract_id: str, intent: str) -> dict[str, Any] | None:
        """Get the latest completed job for a contract and intent."""
        collection = cls.get_collection("analysis_jobs")
        return await collection.find_one(
            {"contract_id": contract_id, "intent": intent, "status": "completed"},
            sort=[("created_at", -1)]
        )

    @classmethod
    async def insert_analysis_job(cls, job_data: dict[str, Any]) -> str:
        """Insert a new analysis job."""
        collection = cls.get_collection("analysis_jobs")
        result = await collection.insert_one(job_data)
        return job_data.get("job_id", str(result.inserted_id))


    @staticmethod
    def vector_search_index_definition() -> dict:
        """
        Returns the Atlas Vector Search index definition for the *chunks* collection.

        The 'vectorSearch' type (GA since MongoDB 7.0 / Atlas 2024-Q1) supports
        pre-filtering on scalar fields declared as 'filter' entries.  This lets
        $vectorSearch restrict the candidate pool to a specific contract_id
        *before* the ANN sweep — much faster than a post-filter.

        Embedding dimensions: 1024  (voyage-3)
        Similarity metric:    cosine
        """
        return {
            "name": "chunk_embedding_index",
            "type": "vectorSearch",
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 1024,
                    "similarity": "cosine",
                },
                # Pre-filter fields — enable contract-scoped and level-scoped ANN
                {"type": "filter", "path": "contract_id"},
                {"type": "filter", "path": "chunk_level"},
                {"type": "filter", "path": "section_type_tags"},
            ],
        }


# Convenience functions
async def connect_db() -> None:
    """Connect to MongoDB."""
    await MongoDB.connect()
    await MongoDB.create_indexes()


async def disconnect_db() -> None:
    """Disconnect from MongoDB."""
    await MongoDB.disconnect()
