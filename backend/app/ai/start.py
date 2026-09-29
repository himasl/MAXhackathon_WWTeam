"""Container entry point: prepare the LLM, load the knowledge base, start /ask."""

import os
import time

from rag import COLLECTION_NAME, LLM_MODEL, QDRANT_PATH, USES_CLOUD_LLM, llm, qdrant


def wait_for_qdrant() -> None:
    for _ in range(60):
        try:
            qdrant.get_collections()
            return
        except Exception:  # noqa: BLE001 - the Qdrant server is still starting
            time.sleep(2)
    raise SystemExit("Qdrant is not reachable")


def main() -> None:
    if USES_CLOUD_LLM:
        print(f"LLM {LLM_MODEL} runs in Ollama Cloud: nothing to download", flush=True)
    else:
        print(f"Pulling {LLM_MODEL} into Ollama (first start only)…", flush=True)
        llm.pull(LLM_MODEL)
    wait_for_qdrant()
    if not qdrant.collection_exists(COLLECTION_NAME) or os.getenv("RAG_REINGEST") == "1":
        import ingest

        ingest.main()
    if QDRANT_PATH:
        # A local Qdrant folder is locked by its client: release it for the API process.
        qdrant.close()
    os.execvp("uvicorn", ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8090"])


if __name__ == "__main__":
    main()
