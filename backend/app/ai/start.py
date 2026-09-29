"""Container entry point: pull the LLM into Ollama, load the knowledge base, start /ask."""

import os
import time

import ollama
from qdrant_client import QdrantClient
from rag import COLLECTION_NAME, LLM_MODEL, QDRANT_URL


def wait_for_qdrant() -> QdrantClient:
    client = QdrantClient(url=QDRANT_URL)
    for _ in range(60):
        try:
            client.get_collections()
            return client
        except Exception:  # noqa: BLE001 - Qdrant is still starting
            time.sleep(2)
    raise SystemExit(f"Qdrant is not reachable at {QDRANT_URL}")


def main() -> None:
    print(f"Pulling {LLM_MODEL} into Ollama (first start only)…", flush=True)
    ollama.pull(LLM_MODEL)
    client = wait_for_qdrant()
    if not client.collection_exists(COLLECTION_NAME) or os.getenv("RAG_REINGEST") == "1":
        import ingest

        ingest.main()
    os.execvp("uvicorn", ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8090"])


if __name__ == "__main__":
    main()
