from httpx import AsyncClient


async def test_step_detail_contains_sources(
    client: AsyncClient,
    saved_profile: dict[str, object],
    active_scenario: object,
) -> None:
    route = (await client.post("/api/v1/routes")).json()
    step = route["steps"][0]

    response = await client.get(f"/api/v1/routes/{route['id']}/steps/{step['id']}")

    assert response.status_code == 200
    assert response.json()["sources"] == [
        {
            "id": response.json()["sources"][0]["id"],
            "title": "Демонстрационный источник",
            "url": "https://example.test/source",
            "organization": "Тестовая организация",
            "source_type": "MOCK",
            "region_code": "77",
            "published_at": None,
            "checked_at": None,
        }
    ]
