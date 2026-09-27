from httpx import AsyncClient

from tests.conftest import PROFILE


async def test_get_me_creates_fixed_development_user(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")

    assert response.status_code == 200
    assert response.json()["max_user_id"] == 123456
    assert response.json()["id"]


async def test_get_missing_profile_uses_error_format(client: AsyncClient) -> None:
    response = await client.get("/api/v1/profile")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "PROFILE_NOT_FOUND", "message": "Profile was not found"}
    }


async def test_put_and_get_profile(client: AsyncClient) -> None:
    saved = await client.put("/api/v1/profile", json=PROFILE)
    loaded = await client.get("/api/v1/profile")

    expected = {**PROFILE, "citizenship": "RU", "university_code": None}
    assert saved.status_code == 200
    assert saved.json() == expected
    assert loaded.status_code == 200
    assert loaded.json() == expected


async def test_validation_error_uses_error_format(client: AsyncClient) -> None:
    invalid = {**PROFILE, "age": "18"}

    response = await client.put("/api/v1/profile", json=invalid)

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed"}
    }


async def test_age_outside_14_100_is_rejected(client: AsyncClient) -> None:
    for age in (-5, 0, 13, 101, 300):
        response = await client.put("/api/v1/profile", json={**PROFILE, "age": age})
        assert response.status_code == 422, age
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    for age in (14, 100):
        response = await client.put("/api/v1/profile", json={**PROFILE, "age": age})
        assert response.status_code == 200, age
