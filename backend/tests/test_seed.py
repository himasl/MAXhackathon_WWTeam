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

    scenarios = ScenarioLoader(DATA_DIR).load_all()
    async with async_session() as session:
        assert await session.scalar(select(func.count()).select_from(Scenario)) == len(scenarios)
        sources = await session.scalar(select(func.count()).select_from(Source))
    assert sources == len({source.code for item in scenarios for source in item.sources})


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
            [
                "temporary_registration",
                "oms_check",
                "transport_spb",
                "pushkin_card",
                "university_support",
            ],
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


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"region_code": "16", "university_code": "kfu"},
            [
                "kfu_dormitory_registration",
                "oms_check",
                "clinic_attachment",
                "transport_kazan",
                "pushkin_card",
                "kfu_support",
            ],
        ),
        (
            {"region_code": "78", "university_code": "spbu", "has_clinic_attachment": True},
            [
                "spbu_dormitory_registration",
                "oms_check",
                "transport_spb",
                "pushkin_card",
                "spbu_support",
            ],
        ),
        (
            {"citizenship": "FOREIGN", "region_code": "77"},
            [
                "international_office",
                "migration_registration",
                "fingerprinting",
                "health_insurance",
            ],
        ),
        (
            {"citizenship": "FOREIGN", "region_code": "16", "university_code": "kfu"},
            ["kfu_migration_registration", "kfu_fingerprinting", "health_insurance"],
        ),
    ],
)
async def test_university_and_foreign_routes(
    client: AsyncClient, overrides: dict[str, object], expected: list[str]
) -> None:
    await seed()
    saved = await client.put("/api/v1/profile", json={**PROFILE, **overrides})
    assert saved.status_code == 200

    response = await client.post("/api/v1/routes")

    assert response.status_code == 201
    assert [step["code"] for step in response.json()["steps"]] == expected
    scenario = "foreign_student_v1" if overrides.get("citizenship") else "student_relocation_v1"
    assert response.json()["scenario_code"] == scenario


async def test_university_must_exist_in_region(client: AsyncClient) -> None:
    await seed()

    wrong_region = await client.put(
        "/api/v1/profile", json={**PROFILE, "region_code": "77", "university_code": "kfu"}
    )
    unknown = await client.put("/api/v1/profile", json={**PROFILE, "university_code": "nope"})

    assert wrong_region.status_code == 422
    assert wrong_region.json()["error"]["code"] == "UNKNOWN_UNIVERSITY"
    assert unknown.status_code == 422


async def test_universities_and_config_are_public(client: AsyncClient) -> None:
    await seed()

    all_items = (await client.get("/api/v1/universities")).json()
    kazan = (await client.get("/api/v1/universities", params={"region_code": "16"})).json()
    config = await client.get("/api/v1/config")

    assert {item["code"] for item in all_items} == {"kfu", "spbu", "hse"}
    assert [item["code"] for item in kazan] == ["kfu"]
    assert config.status_code == 200
    assert set(config.json()) == {"bot_username", "bot_url"}


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
