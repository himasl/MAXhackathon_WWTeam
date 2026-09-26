import dataclasses
import json
import time
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.auth import service as auth_service
from app.auth.max_init_data import InitDataError, sign_init_data, validate_init_data
from app.auth.tokens import TokenError, issue_token, verify_token
from app.core.config import settings as app_settings

BOT_TOKEN = "test-bot-token"


async def test_garbage_bearer_token_is_401_not_500(client: AsyncClient) -> None:
    # Headers travel as latin-1, so "«…»" reaches the server as non-ASCII text.
    for token in ("«quoted»", "3f9a\x85e1c", "a.b", "a.b.c", "x" * 500):
        header = f"Bearer {token}".encode("latin-1")
        response = await client.get("/api/v1/me", headers={"Authorization": header})
        assert response.status_code == 401, token


def make_init_data(user_id: int = 777, auth_date: int | None = None, **extra: str) -> str:
    from urllib.parse import urlencode

    params = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "q-1",
        "user": json.dumps({"id": user_id, "first_name": "Аня"}, ensure_ascii=False),
        **extra,
    }
    params["hash"] = sign_init_data(params, BOT_TOKEN)
    return urlencode(params)


@pytest.fixture
def auth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    patched = dataclasses.replace(
        app_settings,
        max_bot_token=BOT_TOKEN,
        secret_key="unit-test-key",
        dev_auth_enabled=False,
        test_access_tokens={"judge-token": 900001},
    )
    monkeypatch.setattr(auth_service, "settings", patched)


def test_valid_init_data_is_accepted() -> None:
    data = validate_init_data(make_init_data(start_param="step_1"), BOT_TOKEN, 3600)

    assert data.user_id == 777
    assert data.first_name == "Аня"
    assert data.start_param == "step_1"


def test_fragment_form_is_accepted() -> None:
    from urllib.parse import quote

    fragment = "#WebAppData=" + quote(make_init_data())
    assert validate_init_data(fragment, BOT_TOKEN, 3600).user_id == 777


@pytest.mark.parametrize(
    "tamper",
    [
        lambda raw: raw.replace("777", "778"),
        lambda raw: raw + "&hash=deadbeef",
        lambda raw: "&".join(part for part in raw.split("&") if not part.startswith("hash=")),
    ],
)
def test_tampered_init_data_is_rejected(tamper: object) -> None:
    assert callable(tamper)
    with pytest.raises(InitDataError):
        validate_init_data(tamper(make_init_data()), BOT_TOKEN, 3600)


def test_wrong_bot_token_is_rejected() -> None:
    with pytest.raises(InitDataError, match="signature"):
        validate_init_data(make_init_data(), "another-token", 3600)


def test_expired_init_data_is_rejected() -> None:
    old = int(time.time()) - 7200
    with pytest.raises(InitDataError, match="expired"):
        validate_init_data(make_init_data(auth_date=old), BOT_TOKEN, 3600)


def test_link_token_is_not_an_access_token() -> None:
    from app.auth.tokens import issue_link_token, verify_subject

    token = issue_link_token(123, "key", 60, now=1000)

    assert verify_subject(token, "key", now=1030).max_user_id == 123
    with pytest.raises(TokenError, match="not an access token"):
        verify_token(token, "key", now=1030)


def test_token_round_trip_and_expiry() -> None:
    user_id = uuid4()
    token = issue_token(user_id, "key", 60, now=1000)

    assert verify_token(token, "key", now=1030) == user_id
    with pytest.raises(TokenError, match="expired"):
        verify_token(token, "key", now=2000)
    with pytest.raises(TokenError):
        verify_token(token, "other-key", now=1030)
    with pytest.raises(TokenError):
        verify_token("garbage", "key")


async def test_login_with_max_then_use_token(client: AsyncClient, auth_settings: None) -> None:
    response = await client.post("/api/v1/auth/max", json={"init_data": make_init_data(555)})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["max_user_id"] == 555
    me = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["max_user_id"] == 555


async def test_login_rejects_forged_init_data(client: AsyncClient, auth_settings: None) -> None:
    forged = make_init_data(555).replace("555", "1")

    response = await client.post("/api/v1/auth/max", json={"init_data": forged})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_request_without_token_is_unauthorized(
    client: AsyncClient, auth_settings: None
) -> None:
    response = await client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "UNAUTHORIZED", "message": "Authentication required"}
    }


async def test_invalid_token_is_unauthorized(client: AsyncClient, auth_settings: None) -> None:
    response = await client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})

    assert response.status_code == 401


async def test_reviewer_test_token(client: AsyncClient, auth_settings: None) -> None:
    response = await client.get("/api/v1/me", headers={"Authorization": "Bearer judge-token"})

    assert response.status_code == 200
    assert response.json()["max_user_id"] == 900001


async def test_dev_auth_is_ignored_in_production(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    patched = dataclasses.replace(
        app_settings, app_env="production", dev_auth_enabled=True
    )
    monkeypatch.setattr(auth_service, "settings", patched)

    response = await client.get("/api/v1/me")

    assert response.status_code == 401


async def test_login_unavailable_without_bot_token(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        auth_service, "settings", dataclasses.replace(app_settings, max_bot_token="")
    )

    response = await client.post("/api/v1/auth/max", json={"init_data": make_init_data()})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_UNAVAILABLE"
