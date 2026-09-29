"""The light RAG that runs inside the «Маршрут» backend (no GPU, no extra server).

* Retrieval: BM25 over the team's knowledge base (app/ai/knowledge_base, 47 cards with
  official sources). With so few cards, word search is enough, and it needs no model in
  memory, so it fits the free Render instance.
* Generation: a model in Ollama Cloud (OLLAMA_API_KEY, LLM_MODEL=gpt-oss:20b) with the
  same system prompt as the full RAG (app/ai/prompt.py): answer only from the found
  cards, cite them by number; links come from the cards, never from the model.

The full RAG with bge-m3 embeddings and Qdrant stays in app/ai (docs/rag.md).
"""

import json
import logging
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.prompt import NO_ANSWER, SYSTEM_PROMPT
from app.assistant.schemas import RagRequest, RagResponse

logger = logging.getLogger(__name__)
KNOWLEDGE_BASE = Path(__file__).resolve().parents[1] / "ai" / "knowledge_base"
TOP_K = 3
_WORD = re.compile(r"[a-zа-яё0-9]+")


class Card(BaseModel):
    id: str
    topic: str = ""
    title: str
    summary: str = ""
    content: str = ""
    source_url: str = ""


def _stems(text: str) -> list[str]:
    """Lower-case words of 3+ letters cut to 5 characters: регистрации -> регис."""
    return [word[:5] for word in _WORD.findall(text.lower()) if len(word) >= 3]


@lru_cache
def load_cards(path: Path = KNOWLEDGE_BASE) -> tuple[Card, ...]:
    cards: list[Card] = []
    for file in sorted(path.rglob("*.json")):
        cards.extend(Card.model_validate(item) for item in json.loads(file.read_text("utf-8")))
    return tuple(cards)


class BM25:
    def __init__(self, cards: tuple[Card, ...], k1: float = 1.5, b: float = 0.75) -> None:
        self.cards = cards
        # The title counts twice: it names what the card is about.
        self.docs = [
            Counter(_stems(f"{card.title} {card.title} {card.summary} {card.content}"))
            for card in cards
        ]
        self.lengths = [sum(doc.values()) for doc in self.docs]
        self.average = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        frequency: Counter[str] = Counter()
        for doc in self.docs:
            frequency.update(doc.keys())
        total = len(self.docs)
        self.idf = {
            term: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for term, count in frequency.items()
        }
        self.k1, self.b = k1, b

    def search(self, query: str, top_k: int = TOP_K) -> list[Card]:
        terms = set(_stems(query))
        scored: list[tuple[float, int]] = []
        for index, doc in enumerate(self.docs):
            score = 0.0
            for term in terms:
                count = doc.get(term, 0)
                if not count:
                    continue
                norm = self.k1 * (1 - self.b + self.b * self.lengths[index] / self.average)
                score += self.idf[term] * count * (self.k1 + 1) / (count + norm)
            if score > 0:
                scored.append((score, index))
        scored.sort(reverse=True)
        return [self.cards[index] for _, index in scored[:top_k]]


@lru_cache
def index() -> BM25:
    return BM25(load_cards())


def _context(cards: list[Card]) -> str:
    return "\n\n".join(
        f"--- ИСТОЧНИК {number} ---\nНазвание:\n{card.title}\nКраткое описание:\n"
        f"{card.summary}\nИнформация:\n{card.content}\nОфициальный источник:\n{card.source_url}"
        for number, card in enumerate(cards, start=1)
    )


def _parse(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        try:
            parsed = json.loads(content[start : end + 1]) if start >= 0 else None
        except json.JSONDecodeError:
            parsed = None
    return parsed if isinstance(parsed, dict) else None


class CloudRagAssistant:
    """Answers with the team's knowledge base and a model in Ollama Cloud."""

    name = "rag"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-oss:20b",
        host: str = "https://ollama.com",
        timeout: float = 30.0,
        think: bool | str = "low",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.url = f"{host.rstrip('/')}/api/chat"
        self.timeout = timeout
        self.think = think
        self.transport = transport

    def _prompt(self, request: RagRequest, cards: list[Card]) -> str:
        route = "\n".join(f"- {step.title}: {step.short_description}" for step in request.route)
        return (
            "USER PROFILE:\n"
            f"Язык: {request.lang}\n"
            f"Регион: {request.region_title or request.region_code or 'не указан'}\n"
            f"Гражданство: {request.citizenship or 'не указано'}\n"
            f"Вуз: {request.university_code or 'не указан'}\n"
            f"Текущий шаг: {request.step.title if request.step else 'не указан'}\n\n"
            f"ROUTE:\n{route or 'нет данных'}\n\n"
            f"CONTEXT:\n{_context(cards)}\n\n"
            f"QUESTION:\n{request.question}"
        )

    async def answer(self, request: RagRequest) -> RagResponse | None:
        query = request.question
        if request.step:
            query = f"{query} {request.step.title}"
        cards = index().search(query)
        if not cards:
            return None
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._prompt(request, cards)},
            ],
            "stream": False,
            "format": "json",
            "think": self.think,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(
                    self.url, json=body, headers={"Authorization": f"Bearer {self.api_key}"}
                )
            response.raise_for_status()
            content = str(response.json()["message"]["content"])
        except httpx.TimeoutException:
            logger.warning("Ollama Cloud timed out after %ss", self.timeout)
            return None
        except httpx.HTTPStatusError as error:
            logger.warning("Ollama Cloud answered %s", error.response.status_code)
            return None
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            logger.warning("Ollama Cloud failed: %s", type(error).__name__)
            return None

        parsed = _parse(content)
        if parsed is None:
            return None
        answer = str(parsed.get("answer", "")).strip()
        if not answer or NO_ANSWER in answer:
            return None
        used = [
            cards[number - 1]
            for number in dict.fromkeys(parsed.get("source_ids") or [])
            if isinstance(number, int) and 1 <= number <= len(cards)
        ]
        try:
            return RagResponse.model_validate(
                {
                    "answer": answer,
                    "sources": [
                        {"title": card.title, "url": card.source_url}
                        for card in used
                        if card.source_url
                    ],
                    "step_code": request.step.code if request.step else None,
                }
            )
        except ValidationError:
            logger.warning("Ollama Cloud answer did not fit the contract")
            return None
