from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import async_session
from app.routes.models import RouteStatus, UserRoute, UserRouteStep
from tests.conftest import PROFILE


async def test_full_route_api_scenario(
    client: AsyncClient,
    saved_profile: dict[str, object],
    active_scenario: object,
) -> None:
    created = await client.post("/api/v1/routes")

    assert created.status_code == 201
    route = created.json()
    assert [step["code"] for step in route["steps"]] == [
        "adult_step",
        "registration_step",
    ]
    assert route["progress"] == {"completed": 0, "total": 2, "percent": 0}

    async with async_session() as session:
        assert await session.scalar(select(func.count()).select_from(UserRoute)) == 1
        assert await session.scalar(select(func.count()).select_from(UserRouteStep)) == 2

    current = await client.get("/api/v1/routes/current")
    assert current.status_code == 200
    assert current.json()["id"] == route["id"]

    first_step = route["steps"][0]
    detail = await client.get(f"/api/v1/routes/{route['id']}/steps/{first_step['id']}")
    assert detail.status_code == 200
    assert detail.json()["code"] == "adult_step"

    first_complete = await client.post(
        f"/api/v1/routes/{route['id']}/steps/{first_step['id']}/complete"
    )
    assert first_complete.status_code == 200
    assert first_complete.json()["progress"] == {
        "completed": 1,
        "total": 2,
        "percent": 50,
    }

    second_step = route["steps"][1]
    completed = await client.post(
        f"/api/v1/routes/{route['id']}/steps/{second_step['id']}/complete"
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["progress"] == {
        "completed": 2,
        "total": 2,
        "percent": 100,
    }

    reopened = await client.post(f"/api/v1/routes/{route['id']}/steps/{first_step['id']}/reopen")
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "ACTIVE"
    assert reopened.json()["progress"] == {
        "completed": 1,
        "total": 2,
        "percent": 50,
    }


async def test_repeated_generation_archives_active_route(
    client: AsyncClient,
    saved_profile: dict[str, object],
    active_scenario: object,
) -> None:
    first = await client.post("/api/v1/routes")
    second = await client.post("/api/v1/routes")

    assert first.status_code == 201
    assert second.status_code == 201
    async with async_session() as session:
        routes = list(await session.scalars(select(UserRoute).order_by(UserRoute.created_at)))
        assert [route.status for route in routes] == [RouteStatus.ARCHIVED, RouteStatus.ACTIVE]


async def test_zero_step_route_is_completed(
    client: AsyncClient,
    active_scenario: object,
) -> None:
    profile = {
        **PROFILE,
        "age": 17,
        "has_registration": True,
        "has_clinic_attachment": False,
    }
    await client.put("/api/v1/profile", json=profile)

    response = await client.post("/api/v1/routes")

    assert response.status_code == 201
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["progress"] == {"completed": 0, "total": 0, "percent": 100}
    async with async_session() as session:
        route = await session.scalar(select(UserRoute))
        assert route is not None
        assert route.completed_at is not None


async def test_create_route_requires_profile(
    client: AsyncClient,
    active_scenario: object,
) -> None:
    response = await client.post("/api/v1/routes")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROFILE_NOT_FOUND"


async def test_create_route_requires_active_scenario(
    client: AsyncClient,
    saved_profile: dict[str, object],
) -> None:
    response = await client.post("/api/v1/routes")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCENARIO_NOT_FOUND"


async def test_missing_route_and_step_use_error_format(
    client: AsyncClient,
    saved_profile: dict[str, object],
    active_scenario: object,
) -> None:
    missing_route = await client.get(f"/api/v1/routes/{uuid4()}/steps/{uuid4()}")
    assert missing_route.status_code == 404
    assert missing_route.json() == {
        "error": {"code": "ROUTE_NOT_FOUND", "message": "Route was not found"}
    }

    route = (await client.post("/api/v1/routes")).json()
    missing_step = await client.get(f"/api/v1/routes/{route['id']}/steps/{uuid4()}")
    assert missing_step.status_code == 404
    assert missing_step.json() == {
        "error": {
            "code": "ROUTE_STEP_NOT_FOUND",
            "message": "Route step was not found",
        }
    }


async def test_invalid_operation_returns_conflict(
    client: AsyncClient,
    saved_profile: dict[str, object],
    active_scenario: object,
) -> None:
    route = (await client.post("/api/v1/routes")).json()
    step = route["steps"][0]

    response = await client.post(f"/api/v1/routes/{route['id']}/steps/{step['id']}/reopen")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_OPERATION"
