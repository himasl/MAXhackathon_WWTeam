import json
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.assistant.cloud_rag import CloudRagAssistant, index, load_cards
from app.assistant.providers import StubAssistant
from app.assistant.service import assistant_mode, build_assistants
from app.core.config import settings
from tests.test_pilot_features import route_for


def test_knowledge_base_loads_and_search_finds_the_topic() -> None:
    cards = load_cards()
    assert len(cards) >= 40 and all(card.source_url.startswith("http") for card in cards)
    titles = [card.title for card in index().search("Кто может получить Пушкинскую карту?")]
    assert "Пушкинск" in titles[0]
    clinic = [card.title for card in index().search("документы для прикрепления к поликлинике")]
    assert "поликлиник" in clinic[0].lower()


def cloud(handler: Any) -> CloudRagAssistant:
    return CloudRagAssistant(
        "test-key", "gpt-oss:20b", "https://ollama.test", 5.0, "low", httpx.MockTransport(handler)
    )


async def test_cloud_rag_answers_with_sources_from_the_cards(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await route_for(client, region_code="77")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        content = 'Ответ: {"answer": "Карту получают граждане РФ 14–22 лет.", "source_ids": [1]}'
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    monkeypatch.setattr(
        "app.assistant.service.build_assistants", lambda: [cloud(handler), StubAssistant()]
    )
    response = await client.post(
        "/api/v1/ask", json={"question": "Кто может получить Пушкинскую карту?"}
    )
    data = response.json()

    assert data["provider"] == "rag" and data["fallback"] is False
    assert data["answer"] == "Карту получают граждане РФ 14–22 лет."
    assert data["sources"] and "Пушкинск" in data["sources"][0]["title"]
    assert data["sources"][0]["url"].startswith("https://")
    body = seen["body"]
    assert seen["url"] == "https://ollama.test/api/chat" and seen["auth"] == "Bearer test-key"
    assert body["model"] == "gpt-oss:20b" and body["think"] == "low" and body["format"] == "json"
    assert body["stream"] is False
    assert "Регион: Москва" in body["messages"][1]["content"]
    assert "--- ИСТОЧНИК 1 ---" in body["messages"][1]["content"]


@pytest.mark.parametrize(
    "reply",
    [
        httpx.Response(401, json={"error": "unauthorized"}),
        httpx.Response(
            200,
            json={
                "message": {
                    "content": '{"answer": "В доступной базе знаний нет точной '
                    'информации по этому вопросу.", "source_ids": []}'
                }
            },
        ),
        httpx.Response(200, json={"message": {"content": "не JSON"}}),
    ],
    ids=["bad-key", "no-answer", "not-json"],
)
async def test_cloud_rag_falls_back_to_the_route(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, reply: httpx.Response
) -> None:
    await route_for(client, region_code="54", housing_type="RENT")
    monkeypatch.setattr(
        "app.assistant.service.build_assistants",
        lambda: [cloud(lambda request: reply), StubAssistant()],
    )
    data = (await client.post("/api/v1/ask", json={"question": "Как сделать регистрацию?"})).json()
    assert data["provider"] == "stub" and data["fallback"] is True


def test_cloud_rag_is_chosen_by_the_api_key() -> None:
    import dataclasses

    with_key = dataclasses.replace(settings, rag_url="", ollama_api_key="k")
    assert assistant_mode(with_key) == "rag-cloud"
    assert isinstance(build_assistants(with_key)[0], CloudRagAssistant)
    both = dataclasses.replace(settings, rag_url="https://rag.test/ask", ollama_api_key="k")
    assert assistant_mode(both) == "rag"
    assert assistant_mode(dataclasses.replace(settings, rag_url="", ollama_api_key="")) == "stub"
