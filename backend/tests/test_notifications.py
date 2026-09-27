import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.bot.handler import BotHandler
from app.bot.runtime import BotRuntime
from app.core.config import settings
from app.core.database import async_session
from app.integrations.max.client import MAXClient
from app.main import app as fastapi_app
from app.notifications.max_sender import MaxMessageSender
from app.notifications.service import NotificationService, OutgoingMessage
from app.routes.models import UserRouteStep
from app.scenarios.loader import ScenarioLoader
from app.scenarios.seed import sync_all
from tests.conftest import PROFILE, awake

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[tuple[int, OutgoingMessage]] = []

    async def send(self, max_user_id: int, message: OutgoingMessage) -> bool:
        self.sent.append((max_user_id, message))
        return True

    async def acknowledge(
        self, callback_id: str, notification: str, replace_text: str | None = None
    ) -> bool:
        return True


@pytest.fixture
def sender(monkeypatch: pytest.MonkeyPatch) -> RecordingSender:
    recording = RecordingSender()
    runtime: BotRuntime = fastapi_app.state.bot
    notifications = NotificationService(recording)
    monkeypatch.setattr(runtime, "notifications", notifications)
    monkeypatch.setattr(runtime, "handler", BotHandler(notifications, async_session))
    return recording


async def seeded_route(client: AsyncClient) -> dict[str, Any]:
    async with async_session() as session:
        await sync_all(session, ScenarioLoader(DATA_DIR))
    await client.put("/api/v1/profile", json=PROFILE)
    response = await client.post("/api/v1/routes")
    assert response.status_code == 201
    route: dict[str, Any] = response.json()
    return route


async def test_route_creation_and_completion_notify(
    client: AsyncClient, sender: RecordingSender
) -> None:
    route = await seeded_route(client)

    assert sender.sent[-1][0] == settings.dev_max_user_id
    assert "Ваш маршрут готов" in sender.sent[-1][1].text
    assert sender.sent[-1][1].start_param == f"step_{route['steps'][0]['id']}"

    for step in route["steps"]:
        await client.post(f"/api/v1/routes/{route['id']}/steps/{step['id']}/complete")

    assert "Маршрут завершён" in sender.sent[-1][1].text
    assert "Следующий шаг" in sender.sent[-2][1].text


async def test_manual_reminder_endpoint(client: AsyncClient, sender: RecordingSender) -> None:
    route = await seeded_route(client)

    response = await client.post(f"/api/v1/routes/{route['id']}/remind")

    assert response.status_code == 200
    assert response.json() == {"sent": True, "step_id": route["steps"][0]["id"]}
    assert sender.sent[-1][1].text.startswith("Напоминание")


async def test_due_reminders_are_sent_once(client: AsyncClient, sender: RecordingSender) -> None:
    route = await seeded_route(client)
    runtime: BotRuntime = fastapi_app.state.bot
    later = awake(datetime.now(UTC) + timedelta(days=7))

    first = await runtime.send_due_reminders(now=later)
    second = await runtime.send_due_reminders(now=later)

    # Only the registration step (7 days) is due; clinic and transport have 14 days.
    assert first == 1
    assert second == 0
    async with async_session() as session:
        reminded = await session.scalars(
            select(UserRouteStep).where(UserRouteStep.reminded_at.is_not(None))
        )
        assert [step.id for step in reminded] == [UUID(route["steps"][0]["id"])]


async def test_bot_start_and_next_commands(client: AsyncClient, sender: RecordingSender) -> None:
    runtime: BotRuntime = fastapi_app.state.bot
    user_id = settings.dev_max_user_id

    await runtime.handler.handle({"update_type": "bot_started", "user": {"user_id": user_id}})
    assert sender.sent[-1][1].text.startswith("Привет!")

    message = {
        "update_type": "message_created",
        "message": {"sender": {"user_id": user_id}, "body": {"text": "/next"}},
    }
    await runtime.handler.handle(message)
    assert "Маршрут ещё не составлен" in sender.sent[-1][1].text

    await seeded_route(client)
    await runtime.handler.handle(message)
    assert "Следующий шаг" in sender.sent[-1][1].text


async def test_webhook_checks_secret(
    client: AsyncClient, sender: RecordingSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    import dataclasses

    import app.main as main_module

    monkeypatch.setattr(
        main_module, "settings", dataclasses.replace(settings, webhook_secret="s3cret_ok")
    )
    update = {"update_type": "bot_started", "user": {"user_id": 42}}

    denied = await client.post("/max/webhook", json=update)
    accepted = await client.post(
        "/max/webhook", json=update, headers={"X-Max-Bot-Api-Secret": "s3cret_ok"}
    )

    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert sender.sent[-1][0] == 42


async def test_max_sender_falls_back_to_link_button() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        button = body["attachments"][0]["payload"]["buttons"][0][0]
        if button["type"] == "open_app":
            return httpx.Response(400, json={"code": "bad", "message": "invalid button"})
        assert request.headers["Authorization"] == "token"
        assert request.url.params["user_id"] == "7"
        return httpx.Response(200, json={"message": {}})

    client = MAXClient("token", "https://max.test", transport=httpx.MockTransport(handler))
    sender = MaxMessageSender(client, "https://app.test", "marshrut_bot", 99, "open_app")
    message = OutgoingMessage(text="Привет", button_text="Открыть", start_param="step_1")

    assert await sender.send(7, message)
    assert await sender.send(7, message)

    types = [body["attachments"][0]["payload"]["buttons"][0][0]["type"] for body in requests]
    assert types == ["open_app", "link", "link"]
    assert requests[1]["attachments"][0]["payload"]["buttons"][0][0]["url"] == (
        "https://app.test/?start=step_1"
    )
    await client.close()


def test_webhook_secret_is_normalised_for_max() -> None:
    import dataclasses
    import re

    plain = dataclasses.replace(settings, webhook_secret="plain_secret-1")
    generated = dataclasses.replace(settings, webhook_secret="TTzK/V7k+yv5=")

    assert plain.max_webhook_secret == "plain_secret-1"
    assert re.fullmatch(r"[0-9a-f]{64}", generated.max_webhook_secret)


async def test_webhook_registration_error_is_redacted(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    import dataclasses

    secret_settings = dataclasses.replace(
        settings, webhook_secret="abc/def+ghi=", public_url="https://app.test"
    )
    runtime = BotRuntime(secret_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(400, json={"message": f"bad secret {body['secret']}"})

    runtime.client = MAXClient("t", "https://max.test", transport=httpx.MockTransport(handler))
    ok = await runtime._subscribe_webhook()

    assert not ok
    assert secret_settings.max_webhook_secret not in caplog.text
    assert "***" in caplog.text
    await runtime.client.close()


async def test_link_mode_sends_signed_login_link(client: AsyncClient) -> None:
    from urllib.parse import parse_qs, urlsplit

    from app.auth.tokens import issue_link_token

    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {}})

    max_client = MAXClient("t", "https://max.test", transport=httpx.MockTransport(handler))
    sender = MaxMessageSender(
        max_client,
        "https://app.test/",
        "marshrut_bot",
        99,
        "link",
        link_token=lambda mid: issue_link_token(mid, settings.signing_key, 600),
    )
    message = OutgoingMessage(text="Hi", button_text="Open", start_param="step_9")

    assert await sender.send(4242, message)

    button = sent[0]["attachments"][0]["payload"]["buttons"][0][0]
    assert button["type"] == "link"
    query = parse_qs(urlsplit(button["url"]).query)
    assert query["start"] == ["step_9"]
    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {query['t'][0]}"})
    assert me.status_code == 200
    assert me.json()["max_user_id"] == 4242
    await max_client.close()


async def test_bot_understands_punctuation_greetings_and_free_text(
    client: AsyncClient, sender: RecordingSender
) -> None:
    runtime: BotRuntime = fastapi_app.state.bot
    user_id = settings.dev_max_user_id
    await seeded_route(client)

    async def say(text: str) -> str:
        await runtime.handler.handle(
            {
                "update_type": "message_created",
                "message": {"sender": {"user_id": user_id}, "body": {"text": text}},
            }
        )
        return sender.sent[-1][1].text

    assert "Следующий шаг" in await say("Что дальше?!")
    assert "Следующий шаг" in await say("дальше.")
    assert (await say("Привет!")).startswith("Привет!")
    free = await say("как сделать регистрацию?")
    assert free.startswith("Похоже, это про шаг")
    assert (await say("🙂")).startswith("Команды:")
    assert (await say("/help")).startswith("Команды:")
    assert (await say("помощь")).startswith("Команды:")
    assert (await say("/unknown")).startswith("Команды:")
    assert (await say("Начать!")).startswith("Привет!")
    assert (await say("Спасибо!")).startswith("Пожалуйста!")


async def test_webhook_without_secret_is_closed_in_production(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import dataclasses

    monkeypatch.setattr(
        "app.main.settings", dataclasses.replace(settings, app_env="production", webhook_secret="")
    )
    response = await client.post("/max/webhook", json={"update_type": "bot_started"})
    assert response.status_code == 401
