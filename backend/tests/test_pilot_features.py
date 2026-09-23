import dataclasses
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from httpx import AsyncClient

from app.api.v1 import public as public_module
from app.auth.tokens import TokenError, issue_calendar_token, verify_subject
from app.bot.handler import BotHandler
from app.bot.runtime import BotRuntime
from app.calendar.ics import step_event
from app.core.config import settings
from app.core.database import async_session
from app.integrations.max.client import MAXClient
from app.main import app as fastapi_app
from app.notifications.max_sender import MaxMessageSender, done_payload, parse_done_payload
from app.notifications.service import NotificationService, OutgoingMessage
from app.scenarios.loader import ScenarioLoader
from app.scenarios.seed import sync_all
from app.stats import service as stats_module
from tests.conftest import PROFILE

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[tuple[int, OutgoingMessage]] = []
        self.acks: list[tuple[str, str, str | None]] = []

    async def send(self, max_user_id: int, message: OutgoingMessage) -> bool:
        self.sent.append((max_user_id, message))
        return True

    async def acknowledge(
        self, callback_id: str, notification: str, replace_text: str | None = None
    ) -> bool:
        self.acks.append((callback_id, notification, replace_text))
        return True


@pytest.fixture
def sender(monkeypatch: pytest.MonkeyPatch) -> RecordingSender:
    recording = RecordingSender()
    runtime: BotRuntime = fastapi_app.state.bot
    notifications = NotificationService(recording)
    monkeypatch.setattr(runtime, "notifications", notifications)
    monkeypatch.setattr(runtime, "handler", BotHandler(notifications, async_session))
    return recording


async def route_for(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    async with async_session() as session:
        await sync_all(session, ScenarioLoader(DATA_DIR))
    await client.put("/api/v1/profile", json={**PROFILE, **overrides})
    response = await client.post("/api/v1/routes")
    assert response.status_code == 201
    route: dict[str, Any] = response.json()
    return route


def callback(step_id: str, callback_id: str = "cb-1") -> dict[str, Any]:
    return {
        "update_type": "message_callback",
        "callback": {
            "callback_id": callback_id,
            "payload": f"done:{step_id}",
            "user": {"user_id": settings.dev_max_user_id},
        },
    }


def test_done_payload_round_trip() -> None:
    step_id = UUID("12345678-1234-5678-1234-567812345678")

    assert parse_done_payload(done_payload(step_id)) == step_id
    assert parse_done_payload("done:garbage") is None
    assert parse_done_payload("other") is None


async def test_step_messages_carry_done_button(
    client: AsyncClient, sender: RecordingSender
) -> None:
    route = await route_for(client)

    message = sender.sent[-1][1]
    assert message.done_step_id == UUID(route["steps"][0]["id"])


async def test_complete_step_from_chat(client: AsyncClient, sender: RecordingSender) -> None:
    route = await route_for(client)
    runtime: BotRuntime = fastapi_app.state.bot
    first = route["steps"][0]

    await runtime.handler.handle(callback(first["id"]))

    assert sender.acks[-1][0] == "cb-1"
    assert sender.acks[-1][2] == f"✅ «{first['title']}» — выполнено"
    assert "Следующий шаг" in sender.sent[-1][1].text
    assert sender.sent[-1][1].done_step_id == UUID(route["steps"][1]["id"])
    current = (await client.get("/api/v1/routes/current")).json()
    assert current["progress"]["completed"] == 1

    await runtime.handler.handle(callback(first["id"], "cb-2"))
    assert sender.acks[-1] == ("cb-2", "Этот шаг уже выполнен", None)

    stats = (await client.get("/api/v1/stats")).json()
    assert stats["steps"]["done_from_chat"] == 1


async def test_callback_for_foreign_step_is_rejected(
    client: AsyncClient, sender: RecordingSender
) -> None:
    await route_for(client)
    runtime: BotRuntime = fastapi_app.state.bot

    await runtime.handler.handle(callback("00000000-0000-0000-0000-000000000000"))

    assert sender.acks[-1][1] == "Шаг не найден"


async def test_start_with_university_code(client: AsyncClient, sender: RecordingSender) -> None:
    async with async_session() as session:
        await sync_all(session, ScenarioLoader(DATA_DIR))
    runtime: BotRuntime = fastapi_app.state.bot

    await runtime.handler.handle(
        {"update_type": "bot_started", "user": {"user_id": 5}, "payload": "kfu"}
    )
    invited = sender.sent[-1][1]
    await runtime.handler.handle(
        {"update_type": "bot_started", "user": {"user_id": 5}, "payload": "unknown"}
    )
    plain = sender.sent[-1][1]

    assert invited.start_param == "uni_kfu"
    assert "КФУ" in invited.text
    assert plain.start_param is None


async def test_max_sender_renders_done_button_and_answers_callback() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"success": True})

    client = MAXClient("t", "https://max.test", transport=httpx.MockTransport(handler))
    sender = MaxMessageSender(client, "https://app.test", "bot", 1, "link")
    step_id = UUID("12345678-1234-5678-1234-567812345678")

    await sender.send(7, OutgoingMessage(text="x", button_text="Открыть", done_step_id=step_id))
    await sender.acknowledge("cb", "ok", replace_text="done")

    buttons = calls[0][1]["attachments"][0]["payload"]["buttons"]
    assert buttons[1] == [
        {"type": "callback", "text": "✅ Выполнено", "payload": f"done:{step_id}"}
    ]
    assert calls[1] == (
        "/answers",
        {"notification": "ok", "message": {"text": "done", "attachments": []}},
    )
    await client.close()


async def test_calendar_link_and_file(client: AsyncClient) -> None:
    route = await route_for(client)
    step = route["steps"][0]

    link = await client.post(f"/api/v1/routes/{route['id']}/steps/{step['id']}/calendar-link")
    assert link.status_code == 200
    path = "/" + link.json()["url"].split("/", 3)[3]

    ics = await client.get(path)
    assert ics.status_code == 200
    assert ics.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in ics.text
    unfolded = ics.text.replace("\r\n ", "")
    assert "SUMMARY:Маршрут: Регистрация по месту пребывания в общежитии" in unfolded

    token = path.removeprefix("/api/v1/calendar/").removesuffix(".ics")
    with pytest.raises(TokenError):
        verify_subject(token, settings.signing_key)
    assert (await client.get("/api/v1/calendar/forged.ics")).status_code == 404


async def test_calendar_link_requires_deadline(client: AsyncClient) -> None:
    route = await route_for(client)
    no_deadline = next(step for step in route["steps"] if step["deadline"] is None)

    response = await client.post(
        f"/api/v1/routes/{route['id']}/steps/{no_deadline['id']}/calendar-link"
    )

    assert response.status_code == 409


def test_ics_folding_keeps_lines_short() -> None:
    from datetime import date

    body = step_event(
        "id", "Очень длинное название шага " * 5, "Описание", date(2026, 10, 1), "https://x"
    )

    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    assert "DTSTART;VALUE=DATE:20261001" in body


async def test_stats_aggregates_and_excludes_reviewers(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    route = await route_for(client, region_code="16", university_code="kfu")
    for step in route["steps"]:
        await client.post(f"/api/v1/routes/{route['id']}/steps/{step['id']}/complete")

    stats = (await client.get("/api/v1/stats")).json()

    assert stats["users"] == 1
    assert stats["routes"] == {"created": 1, "active": 0, "completed": 1, "completion_rate": 1.0}
    assert stats["steps"]["done"] == len(route["steps"])
    assert stats["registration_median_days"] == 0.0
    assert stats["by_university"] == [{"code": "kfu", "title": "КФУ", "routes": 1, "completed": 1}]

    reviewer = dataclasses.replace(settings, test_access_tokens={"t": settings.dev_max_user_id})
    monkeypatch.setattr(stats_module, "settings", reviewer)
    assert (await client.get("/api/v1/stats")).json()["users"] == 0
    assert public_module is not None


async def test_calendar_token_is_not_a_login(client: AsyncClient) -> None:
    token = issue_calendar_token(UUID(int=1), settings.signing_key, 60)

    response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
