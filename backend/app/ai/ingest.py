"""Loads the knowledge base (knowledge_base/**/*.json) into Qdrant.

Run once after Qdrant starts and whenever the knowledge base changes:
    python ingest.py
Each record: id, topic, title, summary, content, source_url, last_checked.
"""

import json
import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from rag import COLLECTION_NAME, QDRANT_URL, embedding_model

KNOWLEDGE_BASE = Path(__file__).parent / "knowledge_base"


def load_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in sorted(KNOWLEDGE_BASE.rglob("*.json")):
        records.extend(json.loads(path.read_text(encoding="utf-8")))
    return records


def main() -> None:
    records = load_records()
    texts = [f"{item['title']}\n{item['summary']}\n{item['content']}" for item in records]
    vectors = embedding_model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    client = QdrantClient(url=QDRANT_URL)
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
    client.create_collection(
        COLLECTION_NAME,
        vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
    )
    client.upsert(
        COLLECTION_NAME,
        points=[
            PointStruct(
                # Stable ids: the same record keeps its point on re-ingest.
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, item["id"])),
                vector=vector.tolist(),
                payload=item,
            )
            for item, vector in zip(records, vectors, strict=True)
        ],
    )
    print(f"Loaded {len(records)} records into {COLLECTION_NAME} at {QDRANT_URL}")


if __name__ == "__main__":
    main()
