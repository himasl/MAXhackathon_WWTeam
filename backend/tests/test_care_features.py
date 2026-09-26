import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.bot.runtime import BotRuntime
from app.core.config import settings
from app.core.database import async_session
from app.main import app as fastapi_app
from app.notifications.max_sender import parse_step_payload, step_payload
from app.routes.models import RouteStepStatus, UserRouteStep
from tests.test_pilot_features import RecordingSender, route_for, sender  # noqa: F401


def action(kind: str, step_id: str, callback_id: str = "cb-1") -> dict[str, object]:
    return {
        "update_type": "message_callback",
        "callback": {
            "callback_id": callback_id,
            "payload": f"{kind}:{step_id}",
            "user": {"user_id": 123456},
        },
    }


def test_step_payloads_round_trip() -> None:
    step_id = UUID("12345678-1234-5678-1234-567812345678")
    assert parse_step_payload(step_payload("snooze", step_id)) == ("snooze", step_id)
    assert parse_step_payload("delete:x") is None


async def test_snooze_from_chat_reminds_tomorrow(
    client: AsyncClient,
    sender: RecordingSender,  # noqa: F811
) -> None:
    route = await route_for(client)
    runtime: BotRuntime = fastapi_app.state.bot
    step = next(item for item in route["steps"] if item["deadline"] is None)

    await runtime.handler.handle(action("snooze", step["id"]))

    assert sender.acks[-1][2] == f"⏰ Напомню завтра о шаге «{step['title']}»"
    now = datetime.now(UTC)
    assert await runtime.send_due_reminders(now + timedelta(hours=2)) == 0
    sent = await runtime.send_due_reminders(now + timedelta(days=1, hours=1))
    assert sent == 1
    reminder = sender.sent[-1][1]
    assert reminder.done_step_id == UUID(step["id"])
    assert reminder.snooze is True
    async with async_session() as session:
        stored = await session.get(UserRouteStep, UUID(step["id"]))
        assert stored is not None and stored.snoozed_until is None


async def test_in_progress_from_chat(
    client: AsyncClient,
    sender: RecordingSender,  # noqa: F811
) -> None:
    route = await route_for(client)
    runtime: BotRuntime = fastapi_app.state.bot
    step = route["steps"][0]

    await runtime.handler.handle(action("doing", step["id"]))

    assert "в процессе" in (sender.acks[-1][2] or "")
    current = (await client.get("/api/v1/routes/current")).json()
    assert current["steps"][0]["status"] == RouteStepStatus.IN_PROGRESS
    # Completing still works for a started step; snoozing a closed one is refused.
    done = await client.post(f"/api/v1/routes/{route['id']}/steps/{step['id']}/complete")
    assert done.status_code == 200
    await runtime.handler.handle(action("snooze", step["id"], "cb-2"))
    assert sender.acks[-1][1].startswith("Шаг уже закрыт")


async def test_checklist_groups_documents_by_place(
    client: AsyncClient,
    sender: RecordingSender,  # noqa: F811
) -> None:
    route = await route_for(client, region_code="54", housing_type="RENT")

    response = await client.get(f"/api/v1/routes/{route['id']}/checklist")
    assert response.status_code == 200
    groups = response.json()["groups"]
    places = {group["place"]: group for group in groups}
    assert "Госуслуги или МФЦ" in places
    titles = [document["title"] for document in places["Госуслуги или МФЦ"]["documents"]]
    assert titles[0] == "Паспорт гражданина РФ" or "Паспорт" in " ".join(titles)
    codes = [d["code"] for group in groups for d in group["documents"]]
    assert len(codes) >= len(groups)

    sent = await client.post(f"/api/v1/routes/{route['id']}/checklist/send")
    assert sent.json() == {"sent": True}
    assert sender.sent[-1][1].text.startswith("Что взять с собой")


async def test_parent_link_shows_progress_and_can_be_revoked(client: AsyncClient) -> None:
    route = await route_for(client)
    link = await client.post("/api/v1/routes/share")
    assert link.status_code == 200
    token = link.json()["url"].split("share=", 1)[1]

    shared = await client.get(f"/api/v1/shared/{token}")
    assert shared.status_code == 200
    body = shared.json()
    assert body["progress"]["total"] == route["progress"]["total"]
    assert [step["title"] for step in body["steps"]] == [s["title"] for s in route["steps"]]
    assert "max_user_id" not in shared.text and "region_code" not in shared.text

    assert (await client.delete("/api/v1/routes/share")).status_code == 204
    assert (await client.get(f"/api/v1/shared/{token}")).status_code == 404
    assert (await client.get("/api/v1/shared/forged")).status_code == 404


async def test_help_topics_in_two_languages(client: AsyncClient) -> None:
    russian = (await client.get("/api/v1/help")).json()
    english = (await client.get("/api/v1/help", headers={"Accept-Language": "en"})).json()

    assert len(russian) >= 6
    assert russian[0]["phones"][0]["number"] == "112"
    assert english[0]["title"] == "I need help urgently"
    assert english[0]["phones"][0] == {"label": "Emergency", "number": "112"}
    assert all(topic["sources"] for topic in russian)


async def test_foreign_route_in_english(client: AsyncClient) -> None:
    route = await route_for(client, citizenship="FOREIGN", has_registration=False)
    english = await client.get("/api/v1/routes/current", headers={"Accept-Language": "en-US"})

    titles = [step["title"] for step in english.json()["steps"]]
    assert "Health insurance" in titles
    step = next(item for item in english.json()["steps"] if item["title"] == "Health insurance")
    detail = await client.get(
        f"/api/v1/routes/{route['id']}/steps/{step['id']}", headers={"Accept-Language": "en"}
    )
    assert detail.json()["documents"][0]["title"] == "National passport"
    russian = (await client.get("/api/v1/routes/current")).json()
    assert "Медицинское страхование" in [item["title"] for item in russian["steps"]]


async def test_step_report_goes_to_support_chat(
    client: AsyncClient,
    sender: RecordingSender,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import routes as routes_module

    monkeypatch.setattr(
        routes_module, "settings", dataclasses.replace(settings, support_max_user_ids=(4242,))
    )
    route = await route_for(client, region_code="54", housing_type="RENT")
    step = next(item for item in route["steps"] if item["code"] == "temporary_registration")
    url = f"/api/v1/routes/{route['id']}/steps/{step['id']}/report"

    first = await client.post(url, json={"kind": "OUTDATED", "comment": "Адрес МФЦ сменился"})
    assert first.status_code == 201
    to_support = [message for user_id, message in sender.sent if user_id == 4242]
    assert len(to_support) == 1
    text = to_support[0].text
    assert "Регистрация по месту пребывания" in text and "Адрес МФЦ сменился" in text
    assert "Регион: 54" in text and "Источник: https://" in text

    again = await client.post(url, json={"kind": "OUTDATED"})
    assert again.json()["id"] == first.json()["id"]
    assert len([1 for user_id, _ in sender.sent if user_id == 4242]) == 1

    bad = await client.post(url, json={"kind": "SPAM"})
    assert bad.status_code == 422
    stats = (await client.get("/api/v1/stats")).json()
    assert stats["steps"]["reported"] == 1


async def test_health_reports_database_and_version(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "review-123456"})
    body = response.json()
    assert body["status"] == "ok" and body["database"] == "ok" and body["version"]
    assert response.headers["X-Request-ID"] == "review-123456"
    assert len((await client.get("/health")).headers["X-Request-ID"]) == 12
