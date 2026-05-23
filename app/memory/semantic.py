"""Semantic memory — key-value store for learned facts, user preferences, contract summaries."""

import time
from typing import Any
from app.db.mongodb import MongoDB


class SemanticMemory:
    """Persistent key-value store for learned facts with source tracking."""

    def __init__(self):
        self.collection_name = "semantic_memory"

    async def store(self, key: str, value: Any, source: str = "agent", confidence: float = 1.0) -> str:
        """Store or update a fact."""
        doc = {
            "key": key,
            "value": value,
            "source": source,
            "confidence": confidence,
            "last_used": time.time(),
        }
        collection = MongoDB.get_collection(self.collection_name)
        await collection.update_one(
            {"key": key},
            {"$set": doc},
            upsert=True,
        )
        return key

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        """Retrieve a fact by key."""
        collection = MongoDB.get_collection(self.collection_name)
        result = await collection.find_one({"key": key})
        if result:
            # Update last_used
            await collection.update_one({"key": key}, {"$set": {"last_used": time.time()}})
        return result

    async def query(self, key_prefix: str = "", limit: int = 20) -> list[dict[str, Any]]:
        """Query facts by key prefix."""
        collection = MongoDB.get_collection(self.collection_name)
        query = {"key": {"$regex": f"^{key_prefix}", "$options": "i"}} if key_prefix else {}
        cursor = collection.find(query).sort("last_used", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def list_all(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all stored facts."""
        collection = MongoDB.get_collection(self.collection_name)
        cursor = collection.find().sort("last_used", -1).limit(limit)
        return await cursor.to_list(length=limit)
