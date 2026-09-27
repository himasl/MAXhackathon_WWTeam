"""Who answers a student's question.

* ``RagAssistant`` — the external RAG service at ``RAG_URL`` (docs/rag.md has the contract).
* ``StubAssistant`` — the built-in stand-in: finds the step of the student's own route
  the question is about and answers with that step's text and official sources.

Both implement ``Assistant``: to plug in another engine, implement ``answer`` and add it
to ``build_assistants`` in app/assistant/service.py.
"""

import logging
import re
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.assistant.schemas import RagRequest, RagResponse, RagStep

logger = logging.getLogger(__name__)


class Assistant(Protocol):
    name: str

    async def answer(self, request: RagRequest) -> RagResponse | None:
        """An answer, or None when this assistant has nothing to say or is unavailable."""
        ...


class RagAssistant:
    """POST ``RAG_URL`` with ``RagRequest`` as JSON, expects ``RagResponse`` back."""

    name = "rag"

    def __init__(
        self,
        url: str,
        token: str | None = None,
        timeout: float = 8.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url
        self.token = token
        self.timeout = timeout
        self.transport = transport

    async def answer(self, request: RagRequest) -> RagResponse | None:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(
                    self.url, json=request.model_dump(mode="json"), headers=headers
                )
            if response.status_code == 204:
                return None
            response.raise_for_status()
            return RagResponse.model_validate(response.json())
        except httpx.TimeoutException:
            logger.warning("RAG service timed out after %ss", self.timeout)
        except httpx.HTTPStatusError as error:
            logger.warning("RAG service answered %s", error.response.status_code)
        except (httpx.HTTPError, ValueError, ValidationError) as error:
            logger.warning("RAG service failed: %s", type(error).__name__)
        return None


# ---- the built-in stand-in ----

_WORD = re.compile(r"[a-zа-яё0-9]+")
_STOP_WORDS = (
    "как что где когда куда какие какой нужно надо можно мне меня мой моя для это "
    "или если при про после нет есть там тут так уже ещё еще сделать делать "
    "how what where when which the and for can need should does with about have get my"
)
_STOP = frozenset(_STOP_WORDS.split())


def _stems(text: str) -> set[str]:
    """Crude stems: lower-case words of 3+ letters, cut to 5 characters (регистрации →
    регис), without common question words. Enough to match a question to a step."""
    return {
        word[:5] for word in _WORD.findall(text.lower()) if len(word) >= 3 and word not in _STOP
    }


def _score(question: set[str], step: RagStep) -> int:
    title = _stems(step.title)
    body = _stems(f"{step.short_description} {step.full_description} {step.location}")
    return sum(3 if stem in title else 1 if stem in body else 0 for stem in question)


class StubAssistant:
    name = "stub"

    async def answer(self, request: RagRequest) -> RagResponse | None:
        question = _stems(request.question)
        ranked = sorted(request.route, key=lambda step: _score(question, step), reverse=True)
        best = ranked[0] if ranked and _score(question, ranked[0]) > 0 else None
        step = best or request.step
        if step is None:
            return None
        en = request.lang == "en"
        if best is not None:
            head = (
                f"This looks like the step “{step.title}”."
                if en
                else f"Похоже, это про шаг «{step.title}»."
            )
        else:
            head = (
                f"I have no exact answer yet. Here is what the step “{step.title}” says."
                if en
                else f"Точного ответа у меня пока нет. Вот что сказано в шаге «{step.title}»."
            )
        parts = [head, step.short_description]
        if step.location:
            parts.append(
                f"Where to go: {step.location}" if en else f"Куда обратиться: {step.location}"
            )
        parts.append(
            "Exact conditions are in the official source below."
            if en
            else "Точные условия — в официальном источнике ниже."
        )
        return RagResponse.model_validate(
            {
                "answer": "\n\n".join(part for part in parts if part),
                "sources": [source.model_dump() for source in step.sources],
                "step_code": step.code,
            }
        )
