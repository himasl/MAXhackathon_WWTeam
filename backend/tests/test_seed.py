from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import async_session
from app.scenarios.loader import ScenarioLoader
from app.scenarios.models import Scenario
from app.scenarios.seed import sync_all
from app.sources.models import Source, SourceType
from tests.conftest import PROFILE

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"


async def seed() -> None:
    async with async_session() as session:
        await sync_all(session, ScenarioLoader(DATA_DIR))


def test_repository_scenario_file_is_valid() -> None:
    scenario = ScenarioLoader(DATA_DIR).load("student_relocation_v1")

    assert scenario.is_active
    assert {source.source_type for source in scenario.sources} >= {
        SourceType.OFFICIAL,
        SourceType.MOCK,
    }
    for step in scenario.steps:
        assert step.reason, step.code
        assert step.sources, step.code


async def test_seed_is_idempotent() -> None:
    await seed()
    await seed()

    async with async_session() as session:
        assert await session.scalar(select(func.count()).select_from(Scenario)) == 1
        sources = await session.scalar(select(func.count()).select_from(Source))
    assert sources == len(ScenarioLoader(DATA_DIR).load("student_relocation_v1").sources)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"region_code": "77"},
            [
                "dormitory_registration",
                "oms_check",
                "clinic_attachment",
                "transport_moscow",
                "pushkin_card",
                "university_support",
            ],
        ),
        (
            {"region_code": "78", "housing_type": "RENT", "has_clinic_attachment": True},
            ["temporary_registration", "oms_check", "transport_spb", "pushkin_card",
             "university_support"],
        ),
        (
            {"region_code": "16", "age": 25, "has_registration": True},
            ["oms_check", "clinic_attachment", "transport_kazan", "university_support"],
        ),
        (
            {"region_code": "00", "education_type": "PART_TIME", "has_registration": True},
            ["oms_check", "clinic_attachment", "pushkin_card", "university_support"],
        ),
    ],
)
async def test_seeded_route_for_regions(
    client: AsyncClient, overrides: dict[str, object], expected: list[str]
) -> None:
    await seed()
    await client.put("/api/v1/profile", json={**PROFILE, **overrides})

    response = await client.post("/api/v1/routes")

    assert response.status_code == 201
    assert [step["code"] for step in response.json()["steps"]] == expected


async def test_step_detail_explains_itself(client: AsyncClient) -> None:
    await seed()
    await client.put("/api/v1/profile", json=PROFILE)
    route = (await client.post("/api/v1/routes")).json()
    first = route["steps"][0]

    detail = (await client.get(f"/api/v1/routes/{route['id']}/steps/{first['id']}")).json()

    assert detail["code"] == "dormitory_registration"
    assert "общежитии" in detail["reason"]
    assert detail["location"]
    assert detail["deadline"] is not None
    assert detail["deadline_origin"] == "calculated"
    assert {item["code"] for item in detail["documents"]} == {
        "passport",
        "student_id",
        "dormitory_contract",
    }
    assert detail["sources"][0]["source_type"] == "OFFICIAL"
    assert detail["sources"][0]["checked_at"] is not None
    assert detail["next_step_id"] == route["steps"][1]["id"]
