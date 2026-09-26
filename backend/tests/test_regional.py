from typing import Any

from httpx import AsyncClient

from app.regions.catalog import region_codes
from app.regions.services import (
    RegionalPack,
    apply_regional_pack,
    load_regional_pack,
    source_code,
)
from app.scenarios.loader import ScenarioLoader
from tests.test_pilot_features import DATA_DIR, route_for

PACK = RegionalPack.model_validate(
    {
        "regions": {
            "54": {
                "mfc": {
                    "organization": "МФЦ НСО",
                    "url": "https://mfc-nso.ru/",
                    "checked_at": "2026-09-26",
                },
                "student_transport": {
                    "city": "Новосибирск",
                    "title": "Карта студента",
                    "url": "https://example.org/nso",
                    "organization": "Оператор",
                    "summary": "Скидка 50%.",
                    "documents": ["passport"],
                    "checked_at": "2026-09-26",
                },
            },
            "70": {
                "student_transport": {
                    "city": "Томск",
                    "step_title": "Проездной в Томске",
                    "title": "Тарифы",
                    "url": "https://example.org/tomsk",
                    "organization": "ТТУ",
                    "summary": "600 ₽ в месяц.",
                    "checked_at": "2026-09-26",
                }
            },
        }
    }
)


def raw_scenario() -> dict[str, Any]:
    return {
        "code": "demo",
        "version": 1,
        "sources": [],
        "steps": [
            {"code": "registration", "title": "Регистрация", "regional_sources": ["mfc"]},
            {
                "code": "transport",
                "title": "Проезд: {city}",
                "reason": "Регион «{region}».",
                "location": "{organization}",
                "rules": [{"field": "education_type", "operator": "EQ", "value": "FULL_TIME"}],
                "regional_template": "student_transport",
                "documents": [{"code": "student_id"}],
            },
            {
                "code": "transport_other",
                "title": "Проезд",
                "rules": [{"field": "region_code", "operator": "NOT_IN", "value": ["77"]}],
                "regional_fallback": "student_transport",
            },
        ],
    }


def test_pack_expands_sources_template_and_fallback() -> None:
    scenario = apply_regional_pack(raw_scenario(), PACK)
    steps = {step["code"]: step for step in scenario["steps"]}

    assert steps["registration"]["sources"] == [source_code("mfc", "54")]
    assert set(steps) == {"registration", "transport_54", "transport_70", "transport_other"}
    assert steps["transport_54"]["title"] == "Проезд: Новосибирск"
    assert steps["transport_54"]["reason"] == "Регион «Новосибирская область»."
    assert steps["transport_54"]["rules"][0] == {
        "field": "region_code",
        "operator": "EQ",
        "value": "54",
    }
    assert steps["transport_54"]["documents"] == [{"code": "passport"}]
    assert steps["transport_70"]["title"] == "Проездной в Томске"
    assert steps["transport_70"]["documents"] == [{"code": "student_id"}]
    assert steps["transport_other"]["rules"][0]["value"] == ["54", "70", "77"]
    assert {source["code"] for source in scenario["sources"]} == {
        "region_mfc_54",
        "region_transport_54",
        "region_transport_70",
    }
    assert all("regional_template" not in step for step in scenario["steps"])


def test_real_pack_is_consistent() -> None:
    pack = load_regional_pack()
    assert set(pack.regions) <= region_codes()
    kinds = [kind for services in pack.regions.values() for kind in services.kinds()]
    assert kinds.count("mfc") >= 60
    assert kinds.count("tfoms") >= 40
    assert kinds.count("student_transport") >= 25
    for services in pack.regions.values():
        for kind in services.kinds():
            assert str(getattr(services, kind).url).startswith("https://")

    scenario = ScenarioLoader(DATA_DIR).load("student_relocation_v1")
    transport = [step for step in scenario.steps if step.category == "TRANSPORT"]
    covered = {
        str(rule.value)
        for step in transport
        for rule in step.rules
        if rule.field == "region_code" and rule.operator == "EQ"
    }
    fallback = next(step for step in transport if step.code == "transport_other_region")
    excluded = next(rule.value for rule in fallback.rules if rule.field == "region_code")
    assert isinstance(excluded, list)
    # Every region gets exactly one transport step: its own or the fallback.
    assert covered == {str(code) for code in excluded}


async def test_regions_expose_coverage(client: AsyncClient) -> None:
    response = await client.get("/api/v1/regions")
    assert response.status_code == 200
    regions = {region["code"]: region for region in response.json()}
    assert regions["54"]["services"] == ["mfc", "tfoms", "student_transport"]
    assert "student_transport" in regions["77"]["services"]


async def test_route_uses_sources_of_the_users_region(client: AsyncClient) -> None:
    route = await route_for(client, region_code="54", housing_type="RENT")
    codes = {step["code"] for step in route["steps"]}
    assert "transport_regional_54" in codes
    assert "transport_other_region" not in codes

    registration = next(step for step in route["steps"] if step["code"] == "temporary_registration")
    detail = await client.get(f"/api/v1/routes/{route['id']}/steps/{registration['id']}")
    sources = detail.json()["sources"]
    regional = [source for source in sources if source["region_code"]]
    assert [source["region_code"] for source in regional] == ["54"]
    assert regional[0]["source_type"] == "OFFICIAL"
    assert any("gosuslugi" in source["url"] for source in sources)


async def test_region_without_data_falls_back(client: AsyncClient) -> None:
    covered = set(load_regional_pack().regions)
    region = next(code for code in sorted(region_codes()) if code not in covered)
    route = await route_for(client, region_code=region, housing_type="RENT")
    codes = {step["code"] for step in route["steps"]}
    assert "transport_other_region" in codes

    registration = next(step for step in route["steps"] if step["code"] == "temporary_registration")
    detail = await client.get(f"/api/v1/routes/{route['id']}/steps/{registration['id']}")
    assert all(source["region_code"] is None for source in detail.json()["sources"])
