import json
import os

import ollama
from prompt import SYSTEM_PROMPT
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Settings come from the environment; defaults are for a local run (docs/rag.md).
# Qdrant: a server (QDRANT_URL) or, with QDRANT_PATH, a local folder without a server.
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_PATH = os.getenv("QDRANT_PATH", "")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "student_knowledge")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
# Ollama: a local server (OLLAMA_HOST, default http://localhost:11434) or Ollama Cloud:
# OLLAMA_API_KEY set -> https://ollama.com with the key and gpt-oss:20b by default.
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL") or ("gpt-oss:20b" if OLLAMA_API_KEY else "qwen3:8b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST") or ("https://ollama.com" if OLLAMA_API_KEY else None)
# Reasoning: "false" for qwen3, "low" / "medium" / "high" for gpt-oss.
_think = os.getenv("LLM_THINK", "low" if LLM_MODEL.startswith("gpt-oss") else "false")
LLM_THINK: bool | str = {"false": False, "true": True}.get(_think.lower(), _think)
USES_CLOUD_LLM = bool(OLLAMA_API_KEY)

TOP_K = int(os.getenv("RAG_TOP_K", "2"))





embedding_model = SentenceTransformer(
    EMBEDDING_MODEL
)


qdrant = QdrantClient(path=QDRANT_PATH) if QDRANT_PATH else QdrantClient(url=QDRANT_URL)

llm = ollama.Client(
    host=OLLAMA_HOST,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"} if OLLAMA_API_KEY else None,
)



def retrieve(question: str, top_k: int = TOP_K):
    """
    Converts question into embedding and searches Qdrant.
    """

    query_vector = embedding_model.encode(
        question,
        normalize_embeddings=True
    ).tolist()

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    ).points

    return results


def build_context(results):
    """
    Converts Qdrant results into clean context for the LLM.
    """

    context_parts = []

    for i, result in enumerate(results, start=1):

        payload = result.payload

        title = payload.get("title", "")
        summary = payload.get("summary", "")
        content = payload.get("content", "")
        source_url = payload.get("source_url", "")

        context_parts.append(
            f"""
--- ИСТОЧНИК {i} ---

Название:
{title}

Краткое описание:
{summary}

Информация:
{content}

Официальный источник:
{source_url}
""".strip()
        )

    return "\n\n".join(context_parts)


def generate_answer(
    question: str,
    context: str,
    language: str = "ru",
    region: str | None = None,
    citizenship: str | None = None,
    current_step: str | None = None,
    route: list | None = None,
):
    """
    Generates answer and source IDs using context and user metadata.
    """

    user_prompt = f"""
USER PROFILE:

Язык: {language}
Регион: {region or "не указан"}
Гражданство: {citizenship or "не указано"}
Текущий шаг: {current_step or "не указан"}

ROUTE:

{route or "нет данных"}

CONTEXT:

{context}

QUESTION:

{question}
""".strip()

    response = llm.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        think=LLM_THINK,
        format="json",
    )

    raw_response = response["message"]["content"]

    try:
        parsed = json.loads(raw_response)
        if not isinstance(parsed, dict):
            raise TypeError("not an object")

    except (json.JSONDecodeError, TypeError):
        # Some models wrap the JSON in text: take the outermost {...}.
        start, end = str(raw_response).find("{"), str(raw_response).rfind("}")
        try:
            parsed = json.loads(str(raw_response)[start : end + 1]) if start >= 0 else None
        except json.JSONDecodeError:
            parsed = None
    if not isinstance(parsed, dict):
        return {
            "answer": "В доступной базе знаний нет точной информации по этому вопросу.",
            "source_ids": [],
        }

    answer = str(parsed.get("answer", "")).strip()

    source_ids = parsed.get("source_ids", [])

    if not isinstance(source_ids, list):
        source_ids = []

    valid_source_ids = []

    for source_id in source_ids:
        if (
            isinstance(source_id, int)
            and 1 <= source_id <= TOP_K
            and source_id not in valid_source_ids
        ):
            valid_source_ids.append(source_id)

    if not answer:
        answer = "В доступной базе знаний нет точной информации по этому вопросу."
        valid_source_ids = []

    NO_ANSWER = (
        "В доступной базе знаний нет точной информации по этому вопросу."
    )

    if NO_ANSWER in answer:
        valid_source_ids = []

    return {
        "answer": answer,
        "source_ids": valid_source_ids,
    }


def get_sources(results, source_ids):
    """
    Converts source IDs selected by the LLM into sources: {"title", "url"}.

    The LLM never generates URLs itself.
    """

    sources = []

    for source_id in source_ids:

        index = source_id - 1

        if index < 0 or index >= len(results):
            continue

        payload = results[index].payload

        source_url = payload.get("source_url")

        if source_url and all(item["url"] != source_url for item in sources):
            sources.append(
                {
                    "title": payload.get("title") or "Официальный источник",
                    "url": source_url,
                }
            )

    return sources


def ask_question(
    question: str,
    language: str = "ru",
    region: str | None = None,
    citizenship: str | None = None,
    current_step: str | None = None,
    route: list | None = None,
):
    """
    Main RAG entry point.

    Receives question + user metadata,
    retrieves relevant documents,
    generates answer,
    and returns answer + only used sources.
    """

    question = question.strip()

    if not question:
        return "", []

    results = retrieve(question)

    if not results:
        return "Не удалось найти информацию в базе.", []

    context = build_context(results)

    generation = generate_answer(
        question=question,
        context=context,
        language=language,
        region=region,
        citizenship=citizenship,
        current_step=current_step,
        route=route,
    )

    answer = generation["answer"]
    source_ids = generation["source_ids"]

    sources = get_sources(
        results,
        source_ids,
    )

    return answer, sources