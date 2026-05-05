#!/usr/bin/env python3
"""
Create or update the Atlas Vector Search index for the chunks collection.

Usage
-----
    # Dry-run (print index definition, don't call API)
    python scripts/create_vector_index.py --dry-run

    # Create / update via Atlas Admin API
    python scripts/create_vector_index.py \\
        --atlas-public-key  <your-public-key> \\
        --atlas-private-key <your-private-key> \\
        --group-id          <your-atlas-project-id> \\
        --cluster-name      <your-cluster-name>

    # Or set env vars instead of flags
    ATLAS_PUBLIC_KEY=... ATLAS_PRIVATE_KEY=... ATLAS_GROUP_ID=... \\
        ATLAS_CLUSTER_NAME=... python scripts/create_vector_index.py

Requirements
------------
    pip install httpx  (already in requirements.txt)

Notes
-----
- The Atlas Admin API requires Digest auth (SCRAM-SHA-1/256 over HTTPS).
- The index type MUST be "vectorSearch" (not the legacy "vector" type).
- Filter paths (contract_id, chunk_level, section_type_tags) must be declared
  in the index definition BEFORE they can be used as $vectorSearch pre-filters.
- This script is idempotent: it will update an existing index if one with the
  same name already exists.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Index definition (mirrors MongoDB.vector_search_index_definition())
# ---------------------------------------------------------------------------

INDEX_DEFINITION = {
    "name": "chunk_embedding_index",
    "type": "vectorSearch",
    "fields": [
        {
            "type": "vector",
            "path": "embedding",
            "numDimensions": 1024,
            "similarity": "cosine",
        },
        # Pre-filter fields — enable contract-scoped ANN (much faster than post-filter)
        {"type": "filter", "path": "contract_id"},
        {"type": "filter", "path": "chunk_level"},
        {"type": "filter", "path": "section_type_tags"},
    ],
}


def print_index_definition() -> None:
    """Print the index definition JSON to stdout."""
    print("\n=== Atlas Vector Search Index Definition ===\n")
    print(json.dumps(INDEX_DEFINITION, indent=2))
    print(
        "\nPaste this in the MongoDB Atlas UI:\n"
        "  Your Cluster > Browse Collections > Search > Create Search Index\n"
        "  > JSON Editor > select collection: chunks\n"
        "  > select type:  Vector Search\n"
        "  > paste the JSON above\n"
    )


def create_index_via_api(
    public_key: str,
    private_key: str,
    group_id: str,
    cluster_name: str,
    db_name: str,
    collection: str = "chunks",
) -> None:
    """Create or update the vector search index using the Atlas Admin API v2."""
    try:
        import httpx
        from httpx import DigestAuth
    except ImportError:
        print("ERROR: httpx is required.  Run: pip install httpx")
        sys.exit(1)

    base = f"https://cloud.mongodb.com/api/atlas/v2/groups/{group_id}/clusters/{cluster_name}/search/indexes"
    auth = DigestAuth(public_key, private_key)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/vnd.atlas.2024-05-30+json",
    }

    # Check if index already exists
    resp = httpx.get(
        f"{base}/{db_name}/{collection}",
        auth=auth,
        headers=headers,
        timeout=30,
    )

    existing_id: str | None = None
    if resp.status_code == 200:
        indexes = resp.json()
        for idx in indexes:
            if idx.get("name") == INDEX_DEFINITION["name"]:
                existing_id = idx.get("indexID") or idx.get("id")
                break

    payload = {
        **INDEX_DEFINITION,
        "database": db_name,
        "collectionName": collection,
    }

    if existing_id:
        # Update existing index
        print(f"Updating existing index (id={existing_id}) ...")
        resp = httpx.patch(
            f"{base}/{existing_id}",
            json=payload,
            auth=auth,
            headers=headers,
            timeout=30,
        )
    else:
        # Create new index
        print("Creating new vector search index ...")
        resp = httpx.post(
            base,
            json=payload,
            auth=auth,
            headers=headers,
            timeout=30,
        )

    if resp.status_code in (200, 201, 202):
        print(f"✓ Success ({resp.status_code}): {resp.json().get('name', INDEX_DEFINITION['name'])}")
        print("Note: index build may take a few minutes.")
    else:
        print(f"✗ API error ({resp.status_code}): {resp.text}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/update Atlas Vector Search index")
    parser.add_argument("--dry-run", action="store_true", help="Print index JSON only, don't call API")
    parser.add_argument("--atlas-public-key",  default=os.environ.get("ATLAS_PUBLIC_KEY"))
    parser.add_argument("--atlas-private-key", default=os.environ.get("ATLAS_PRIVATE_KEY"))
    parser.add_argument("--group-id",          default=os.environ.get("ATLAS_GROUP_ID"))
    parser.add_argument("--cluster-name",      default=os.environ.get("ATLAS_CLUSTER_NAME"))
    parser.add_argument("--db-name",           default=os.environ.get("MONGODB_DB_NAME", "contract_agent"))
    parser.add_argument("--collection",        default="chunks")
    args = parser.parse_args()

    if args.dry_run:
        print_index_definition()
        return

    missing = [
        name for name, val in [
            ("--atlas-public-key",  args.atlas_public_key),
            ("--atlas-private-key", args.atlas_private_key),
            ("--group-id",          args.group_id),
            ("--cluster-name",      args.cluster_name),
        ]
        if not val
    ]
    if missing:
        print(f"ERROR: Missing required arguments: {', '.join(missing)}")
        print("Either pass them as flags or set the corresponding env vars.")
        print_index_definition()
        sys.exit(1)

    create_index_via_api(
        public_key=args.atlas_public_key,
        private_key=args.atlas_private_key,
        group_id=args.group_id,
        cluster_name=args.cluster_name,
        db_name=args.db_name,
        collection=args.collection,
    )


if __name__ == "__main__":
    main()
