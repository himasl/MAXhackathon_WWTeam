"""HTTP service of the RAG assistant: POST /ask, the contract of docs/rag.md.

Run from this folder:  uvicorn api:app --port 8090
The «Маршрут» backend calls it when RAG_URL=http://<host>:8090/ask is set.
"""

import logging
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel
from rag import ask_question

logger = logging.getLogger("rag")
app = FastAPI(title="Маршрут — RAG-помощник")
# Optional: the same value as RAG_TOKEN in the «Маршрут» backend.
TOKEN = os.getenv("RAG_TOKEN", "")
NO_ANSWER = "В доступной базе знаний нет точной информации по этому вопросу."


class Step(BaseModel):
    code: str = ""
    title: str = ""
    short_description: str = ""
    full_description: str = ""
    location: str = ""
    sources: list[dict[str, Any]] = []


class Question(BaseModel):
    """What the «Маршрут» backend sends (docs/rag.md). The older field names
    (language, region, current_step) are still accepted."""

    question: str
    lang: str | None = None
    language: str | None = None
    region_code: str | None = None
    region_title: str | None = None
    region: str | None = None
    citizenship: str | None = None
    university_code: str | None = None
    step: Step | None = None
    current_step: str | None = None
    route: list[dict[str, Any]] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=None)
def ask(
    data: Question, authorization: str | None = Header(default=None)
) -> dict[str, Any] | Response:
    if TOKEN and authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="bad token")
    step = data.step
    try:
        answer, sources = ask_question(
            question=data.question,
            language=data.lang or data.language or "ru",
            region=data.region_title or data.region or data.region_code,
            citizenship=data.citizenship,
            current_step=(step.title if step else None) or data.current_step,
            route=[
                {"title": item.get("title"), "short_description": item.get("short_description")}
                for item in data.route or []
            ],
        )
    except Exception as error:
        logger.exception("RAG failed")
        raise HTTPException(status_code=503, detail="RAG is unavailable") from error
    if not answer or answer.startswith(NO_ANSWER):
        # 204 tells the backend "no answer": it answers from the route instead.
        return Response(status_code=204)
    return {
        "answer": answer,
        "sources": sources,
        "step_code": step.code if step and step.code else None,
    }
