import json
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.assistant.providers import RagAssistant, StubAssistant
from app.bot.handler import BotHandler
from app.bot.runtime import BotRuntime
from app.core.config import settings
from app.core.database import async_session
from app.main import app as fastapi_app
from app.notifications.service import NotificationService
from tests.test_pilot_features import RecordingSender, route_for, sender  # noqa: F401


def use_assistants(monkeypatch: pytest.MonkeyPatch, *assistants: object) -> None:
    monkeypatch.setattr("app.assistant.service.build_assistants", lambda: list(assistants))


def rag(handler: Any) -> RagAssistant:
    return RagAssistant("https://rag.test/ask", "secret", 1.0, httpx.MockTransport(handler))


async def ask(client: AsyncClient, question: str, step_id: str | None = None) -> dict[str, Any]:
    response = await client.post("/api/v1/ask", json={"question": question, "step_id": step_id})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_stub_finds_the_step_the_question_is_about(client: AsyncClient) -> None:
    route = await route_for(client, region_code="54", housing_type="RENT")
    registration = next(s for s in route["steps"] if s["code"] == "temporary_registration")

    answer = await ask(client, "Как сделать регистрацию по новому адресу?")

    assert answer["provider"] == "stub" and answer["fallback"] is False
    assert answer["step_id"] == registration["id"]
    assert answer["answer"].startswith("Похоже, это про шаг «Регистрация по месту пребывания»")
    assert answer["sources"] and answer["sources"][0]["url"].startswith("https://")


async def test_stub_answers_about_the_open_step_when_nothing_matches(client: AsyncClient) -> None:
    route = await route_for(client, region_code="77")
    step = route["steps"][0]

    answer = await ask(client, "Сколько это займёт?", step["id"])

    assert answer["answer"].startswith("Точного ответа у меня пока нет")
    assert answer["step_id"] == step["id"]


async def test_without_a_route_the_student_is_asked_to_build_one(client: AsyncClient) -> None:
    answer = await ask(client, "Как прикрепиться к поликлинике?")
    assert answer["provider"] == "none" and answer["sources"] == []
    assert "Сначала ответьте на несколько вопросов" in answer["answer"]


async def test_rag_gets_the_context_and_its_answer_is_used(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    route = await route_for(client, region_code="54", housing_type="RENT")
    clinic = next(s for s in route["steps"] if s["code"] == "clinic_attachment")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "answer": "Возьмите паспорт и полис ОМС.",
                "sources": [{"title": "Госуслуги", "url": "https://www.gosuslugi.ru/"}],
                "step_code": "clinic_attachment",
            },
        )

    use_assistants(monkeypatch, rag(handler), StubAssistant())
    answer = await ask(client, "Что взять в поликлинику?", clinic["id"])

    assert answer == {
        "answer": "Возьмите паспорт и полис ОМС.",
        "sources": [{"title": "Госуслуги", "url": "https://www.gosuslugi.ru/", "organization": ""}],
        "step_id": clinic["id"],
        "provider": "rag",
        "fallback": False,
    }
    body = seen["body"]
    assert seen["auth"] == "Bearer secret"
    assert body["question"] == "Что взять в поликлинику?" and body["lang"] == "ru"
    assert body["region_code"] == "54" and body["region_title"] == "Новосибирская область"
    assert body["citizenship"] == "RU"
    assert body["step"]["code"] == "clinic_attachment"
    assert {step["code"] for step in body["route"]} == {step["code"] for step in route["steps"]}


@pytest.mark.parametrize(
    "failure",
    [
        lambda request: httpx.Response(500, json={"error": "boom"}),
        lambda request: httpx.Response(200, json={"unexpected": True}),
        lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=request)),
    ],
    ids=["server-error", "bad-contract", "timeout"],
)
async def test_rag_failure_falls_back_to_the_stub(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, failure: Any
) -> None:
    await route_for(client, region_code="54", housing_type="RENT")
    use_assistants(monkeypatch, rag(failure), StubAssistant())

    answer = await ask(client, "Как сделать регистрацию?")

    assert answer["provider"] == "stub" and answer["fallback"] is True


async def test_question_is_validated(client: AsyncClient) -> None:
    for payload in ({"question": "?"}, {"question": "x" * 501}, {"text": "где МФЦ"}):
        assert (await client.post("/api/v1/ask", json=payload)).status_code == 422


async def test_bot_answers_free_text_with_sources_and_a_step_button(
    client: AsyncClient,
    sender: RecordingSender,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = await route_for(client, region_code="54", housing_type="RENT")
    registration = next(s for s in route["steps"] if s["code"] == "temporary_registration")
    runtime: BotRuntime = fastapi_app.state.bot
    monkeypatch.setattr(runtime, "handler", BotHandler(NotificationService(sender), async_session))

    await runtime.handler.handle(
        {
            "update_type": "message_created",
            "message": {
                "sender": {"user_id": settings.dev_max_user_id},
                "body": {"text": "как сделать регистрацию?"},
            },
        }
    )

    message = sender.sent[-1][1]
    assert message.text.startswith("Похоже, это про шаг «Регистрация по месту пребывания»")
    assert "проверяйте по официальному источнику" in message.text
    assert message.start_param == f"step_{registration['id']}"
    assert message.extra_links and message.extra_links[0][1].startswith("https://")


def test_health_tells_which_assistant_answers() -> None:
    from fastapi.testclient import TestClient

    assert TestClient(fastapi_app).get("/health").json()["assistant"] == "stub"


async def test_questions_are_rate_limited(client: AsyncClient) -> None:
    await route_for(client, region_code="77")
    for _ in range(10):
        assert (await client.post("/api/v1/ask", json={"question": "где МФЦ"})).status_code == 200
    limited = await client.post("/api/v1/ask", json={"question": "где МФЦ"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.headers["Retry-After"] == "60"


def test_rate_limiter_window() -> None:
    from app.core.rate_limit import RateLimiter

    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("u", now=0) and limiter.allow("u", now=1)
    assert not limiter.allow("u", now=2)
    assert limiter.allow("other", now=2)
    assert limiter.allow("u", now=61)
