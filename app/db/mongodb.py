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

        # Vector search index info (created via Atlas UI or shell)
        # Print instructions if index doesn't exist
        try:
            indexes = await chunks.list_indexes().to_list(None)
            has_vector_index = any(
                idx.get("name") == "chunk_embedding_index" for idx in indexes
            )
            if not has_vector_index:
                print("""
Vector Search index not found. Create it in MongoDB Atlas or run:

db.chunks.createIndex({
  name: "chunk_embedding_index",
  key: { embedding: "vector" },
  numDimensions: 1024,
  similarity: "cosine"
})

Or in Atlas UI: Collections > chunks > Create Index > Vector Search
""")
        except Exception:
            pass  # Index check failed, continue

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


# Convenience functions
async def connect_db() -> None:
    """Connect to MongoDB."""
    await MongoDB.connect()
    await MongoDB.create_indexes()


async def disconnect_db() -> None:
    """Disconnect from MongoDB."""
    await MongoDB.disconnect()
