from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.admin import activity
from app.bot.handler import BotHandler
from app.bot.runtime import BotRuntime
from app.core.config import settings
from app.core.database import async_session
from app.main import app as fastapi_app
from app.notifications.service import NotificationService
from app.scenarios.loader import ScenarioLoader
from app.scenarios.seed import sync_all
from app.sources.models import Source
from tests.test_pilot_features import RecordingSender, route_for, sender  # noqa: F401

ADMIN = settings.dev_max_user_id


@pytest.fixture(autouse=True)
def fresh_activity_cache() -> None:
    # The database is recreated for every test; so is the "already recorded today" cache.
    activity._seen.clear()


@pytest.fixture
def as_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.admin.access.admin_ids", lambda: frozenset({ADMIN}))


async def test_panel_is_for_the_team_only(client: AsyncClient) -> None:
    me = (await client.get("/api/v1/me")).json()
    assert me["is_admin"] is False
    for path in ("/api/v1/admin/overview", "/api/v1/admin/sources", "/api/v1/admin/reports"):
        response = await client.get(path)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_overview_counts_funnel_and_activity(
    client: AsyncClient,
    as_admin: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The team is excluded from business metrics; count the dev user as a student here.
    monkeypatch.setattr("app.admin.service.excluded_ids", list)
    route = await route_for(client, region_code="54", housing_type="RENT")
    first = route["steps"][0]
    await client.post(f"/api/v1/routes/{route['id']}/steps/{first['id']}/complete")

    assert (await client.get("/api/v1/me")).json()["is_admin"] is True
    response = await client.get("/api/v1/admin/overview")
    assert response.status_code == 200
    data: dict[str, Any] = response.json()

    funnel = {stage["code"]: stage["users"] for stage in data["funnel"]}
    assert funnel == {"opened": 1, "profile": 1, "route": 1, "first_step": 1, "completed": 0}
    assert data["users"]["new_7d"] == 1
    assert data["activity"]["dau"] == 1 and data["activity"]["mau"] == 1
    assert len(data["activity"]["daily"]) == 30
    assert data["activity"]["daily"][-1]["app"] == 1
    assert data["by_region"][0]["code"] == "54" and data["by_region"][0]["users"] == 1
    assert data["by_housing"][0]["title"] == "Снимает жильё"
    assert data["engagement"]["steps_done"] == 1
    assert data["problem_steps"], "steps of the route are listed"
    assert data["data"]["regional_sources"] > 0


async def test_team_is_excluded_from_metrics(client: AsyncClient, as_admin: None) -> None:
    await route_for(client, region_code="77")
    data = (await client.get("/api/v1/admin/overview")).json()
    assert data["users"]["total"] == 0
    assert data["activity"]["mau"] == 0


async def test_source_edit_survives_the_next_seed(client: AsyncClient, as_admin: None) -> None:
    await route_for(client, region_code="54")
    sources = (await client.get("/api/v1/admin/sources", params={"region_code": "54"})).json()
    mfc = next(item for item in sources if item["kind"] == "mfc")
    assert mfc["region_title"] and mfc["steps"] >= 1

    response = await client.patch(
        f"/api/v1/admin/sources/{mfc['id']}",
        json={"url": "https://mfc-nso.ru/new-page", "organization": "МФЦ НСО"},
    )
    assert response.status_code == 200
    edited = response.json()
    assert edited["url"] == "https://mfc-nso.ru/new-page"
    assert edited["edited_at"] is not None and edited["stale"] is False

    assert (
        await client.patch(f"/api/v1/admin/sources/{mfc['id']}", json={"url": "not a url"})
    ).status_code == 422

    async with async_session() as session:
        await sync_all(session, ScenarioLoader())
    async with async_session() as session:
        source = await session.scalar(select(Source).where(Source.code == mfc["code"]))
        assert source is not None and source.url == "https://mfc-nso.ru/new-page"

    only_mfc = (await client.get("/api/v1/admin/sources", params={"kind": "mfc"})).json()
    assert only_mfc and {item["kind"] for item in only_mfc} == {"mfc"}


async def test_reports_can_be_resolved(client: AsyncClient, as_admin: None) -> None:
    route = await route_for(client, region_code="54", housing_type="RENT")
    step = route["steps"][0]
    url = f"/api/v1/routes/{route['id']}/steps/{step['id']}/report"
    await client.post(url, json={"kind": "OUTDATED", "comment": "Сайт не открывается"})

    reports = (await client.get("/api/v1/admin/reports")).json()
    assert len(reports) == 1 and reports[0]["comment"] == "Сайт не открывается"
    assert reports[0]["region_code"] == "54"

    report_id = reports[0]["id"]
    assert (await client.post(f"/api/v1/admin/reports/{report_id}/resolve")).status_code == 204
    assert (await client.get("/api/v1/admin/reports")).json() == []
    resolved = (await client.get("/api/v1/admin/reports", params={"resolved": True})).json()
    assert resolved[0]["resolved_at"] is not None
    assert (await client.post(f"/api/v1/admin/reports/{report_id}/reopen")).status_code == 204
    assert len((await client.get("/api/v1/admin/reports")).json()) == 1
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.post(f"/api/v1/admin/reports/{missing}/resolve")).status_code == 404


async def test_admin_command_and_bot_activity(
    client: AsyncClient,
    sender: RecordingSender,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await route_for(client, region_code="77")
    runtime: BotRuntime = fastapi_app.state.bot
    notifications = NotificationService(sender)
    monkeypatch.setattr(
        runtime, "handler", BotHandler(notifications, async_session, support_ids=(ADMIN,))
    )

    async def say(text: str, user_id: int) -> str:
        await runtime.handler.handle(
            {
                "update_type": "message_created",
                "message": {"sender": {"user_id": user_id}, "body": {"text": text}},
            }
        )
        return sender.sent[-1][1].text

    panel = await say("/admin", ADMIN)
    assert panel.startswith("Панель команды") and sender.sent[-1][1].start_param == "admin"
    assert not (await say("/admin", 555)).startswith("Панель команды")

    async with async_session() as session:
        rows = (await session.execute(select(activity.UserActivity.channel))).scalars().all()
    assert set(rows) == {"app", "bot"}
