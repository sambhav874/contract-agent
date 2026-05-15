"""MongoDB connection and operations."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import settings
from app.db.models import ChunkDocument, ContractMetadata, RawActual, MappingRule


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

        # KPI collection indexes
        kpis = cls.get_collection("kpis")
        await kpis.create_index([("contract_id", 1), ("kpi_id", 1)], unique=True)

        # Actuals collection indexes
        actuals = cls.get_collection("actuals")
        await actuals.create_index([("contract_id", 1), ("kpi_id", 1)])
        await actuals.create_index("timestamp")

        # Breaches collection indexes
        breaches = cls.get_collection("breaches")
        await breaches.create_index("contract_id")
        await breaches.create_index("timestamp")

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
        kpis = cls.get_collection("kpis")
        actuals = cls.get_collection("actuals")
        breaches = cls.get_collection("breaches")

        await contracts.delete_one({"contract_id": contract_id})
        await chunks.delete_many({"contract_id": contract_id})
        await jobs.delete_many({"contract_id": contract_id})
        await kpis.delete_many({"contract_id": contract_id})
        await actuals.delete_many({"contract_id": contract_id})
        await breaches.delete_many({"contract_id": contract_id})

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

    # ── KPI Operations ────────────────────────────────────────────────
    
    @classmethod
    async def upsert_kpis(cls, contract_id: str, kpis: list[dict[str, Any]]) -> int:
        """Insert or update KPIs for a contract."""
        collection = cls.get_collection("kpis")
        count = 0
        for kpi in kpis:
            kpi["contract_id"] = contract_id
            await collection.update_one(
                {"contract_id": contract_id, "kpi_id": kpi["kpi_id"]},
                {"$set": kpi},
                upsert=True
            )
            count += 1
        return count

    @classmethod
    async def get_kpis(cls, contract_id: str) -> list[dict[str, Any]]:
        """Get all KPIs for a contract."""
        collection = cls.get_collection("kpis")
        return await collection.find({"contract_id": contract_id}).to_list(None)

    # ── Operational Actuals ───────────────────────────────────────────

    @classmethod
    async def insert_actual(cls, actual: dict[str, Any]) -> str:
        """Insert an operational actual (performance data)."""
        collection = cls.get_collection("actuals")
        result = await collection.insert_one(actual)
        return str(result.inserted_id)

    @classmethod
    async def get_all_actuals(cls, contract_id: str) -> list[dict[str, Any]]:
        """Get all historical actual values for a contract."""
        collection = cls.get_collection("actuals")
        return await collection.find({"contract_id": contract_id}).sort("timestamp", -1).to_list(None)

    @classmethod
    async def get_latest_actuals(cls, contract_id: str) -> list[dict[str, Any]]:
        """Get the latest actual value for each KPI in a contract."""
        collection = cls.get_collection("actuals")
        # Aggregation to find latest by kpi_id
        pipeline = [
            {"$match": {"contract_id": contract_id}},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$kpi_id",
                "latest": {"$first": "$$ROOT"}
            }},
            {"$replaceRoot": {"newRoot": "$latest"}}
        ]
        return await collection.aggregate(pipeline).to_list(None)

    # ── Raw Actuals & Mappings ───────────────────────────────────────

    @classmethod
    async def insert_raw_actual(cls, raw_actual: dict[str, Any]) -> str:
        """Insert a raw, unmapped actual into staging."""
        collection = cls.get_collection("raw_actuals")
        result = await collection.insert_one(raw_actual)
        return str(result.inserted_id)

    @classmethod
    async def get_pending_raw_actuals(cls, contract_id: str) -> list[dict[str, Any]]:
        """Get all raw actuals that haven't been processed yet."""
        collection = cls.get_collection("raw_actuals")
        return await collection.find({"contract_id": contract_id, "status": "pending"}).to_list(None)

    @classmethod
    async def update_raw_actual_status(cls, raw_id: str, status: str) -> bool:
        """Update the processing status of a raw actual."""
        collection = cls.get_collection("raw_actuals")
        result = await collection.update_one({"raw_id": raw_id}, {"$set": {"status": status}})
        return result.matched_count > 0

    @classmethod
    async def get_raw_actuals(cls, contract_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get the most recent raw actuals for a contract (both pending and processed)."""
        collection = cls.get_collection("raw_actuals")
        return await collection.find({"contract_id": contract_id}).sort("ingested_at", -1).limit(limit).to_list(None)

    @classmethod
    async def get_raw_actuals_by_ids(cls, raw_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch specific raw records by their raw_id."""
        collection = cls.get_collection("raw_actuals")
        return await collection.find({"raw_id": {"$in": raw_ids}}).to_list(None)

    @classmethod
    async def upsert_mapping_rule(cls, rule: dict[str, Any]) -> str:
        """Create or update a mapping rule."""
        collection = cls.get_collection("mapping_rules")
        await collection.update_one(
            {"contract_id": rule["contract_id"], "source_match": rule["source_match"]},
            {"$set": rule},
            upsert=True
        )
        return rule.get("rule_id")

    @classmethod
    async def get_mapping_rules(cls, contract_id: str) -> list[dict[str, Any]]:
        """Get all mapping rules for a contract."""
        collection = cls.get_collection("mapping_rules")
        return await collection.find({"contract_id": contract_id}).to_list(None)

    # ── Breach Results ───────────────────────────────────────────────

    @classmethod
    async def insert_breach(cls, breach: dict[str, Any]) -> str:
        """Insert a breach result."""
        collection = cls.get_collection("breaches")
        result = await collection.insert_one(breach)
        return str(result.inserted_id)

    @classmethod
    async def get_breaches(cls, contract_id: str) -> list[dict[str, Any]]:
        """Get all breach results for a contract."""
        collection = cls.get_collection("breaches")
        return await collection.find({"contract_id": contract_id}).sort("timestamp", -1).to_list(None)

    @classmethod
    async def update_breach(cls, breach_id: str, updates: dict[str, Any]) -> bool:
        """Update a breach result."""
        collection = cls.get_collection("breaches")
        from bson import ObjectId
        
        # Try updating by breach_id string first
        result = await collection.update_one({"breach_id": breach_id}, {"$set": updates})
        if result.matched_count > 0:
            return True
            
        # Try updating by MongoDB _id
        try:
            result = await collection.update_one({"_id": ObjectId(breach_id)}, {"$set": updates})
            return result.matched_count > 0
        except:
            return False

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
