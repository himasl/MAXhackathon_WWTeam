from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import json

from rag import ask_question

app = FastAPI()


class Question(BaseModel):
    question: str
    language: str | None = "ru"
    region: str | None = None
    citizenship: str | None = None
    current_step: str | None = None
    route: list | None = None


@app.post("/ask")
def ask(data: Question):
    answer, sources = ask_question(
        question=data.question,
        language=data.language,
        region=data.region,
        citizenship=data.citizenship,
        current_step=data.current_step,
        route=data.route,
    )

    return {
        "answer": answer,
        "sources": sources
    }