"""Thin async client for the MAX Bot API (https://dev.max.ru/docs-api).

Business services never call this directly: they use ``NotificationService`` through the
``MessageSender`` protocol, which keeps domain logic independent of MAX.
"""

import logging
import ssl
from functools import lru_cache
from pathlib import Path
from typing import Any

import certifi
import httpx

logger = logging.getLogger(__name__)


DEFAULT_CA_BUNDLE = Path(__file__).resolve().parents[3] / "certs" / "russian_trusted_ca.pem"


@lru_cache
def ssl_context(extra_ca_file: str | None = None) -> ssl.SSLContext:
    """Trust public CAs plus the Russian Ministry of Digital Development CA used by MAX."""
    context = ssl.create_default_context(cafile=certifi.where())
    extra = Path(extra_ca_file) if extra_ca_file else DEFAULT_CA_BUNDLE
    if extra.is_file():
        context.load_verify_locations(cafile=str(extra))
    else:
        logger.warning("MAX CA bundle %s not found, using public CAs only", extra)
    return context


class MaxApiError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"MAX API error {status_code}: {message}")
        self.status_code = status_code


class MAXClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        ca_bundle: str | None = None,
    ) -> None:
        # The token goes to the Authorization header only and is never logged.
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": token},
            timeout=timeout,
            transport=transport,
            verify=ssl_context(ca_bundle),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout: float | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {"params": params, "json": json}
        if timeout is not None:
            kwargs["timeout"] = timeout
        response = await self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                message = str(response.json().get("message", response.text))
            except ValueError:
                message = response.text
            raise MaxApiError(response.status_code, message[:300])
        return response.json() if response.content else {}

    async def get_me(self) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", "/me")
        return result

    async def send_message(
        self,
        text: str,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id
        if chat_id is not None:
            params["chat_id"] = chat_id
        body: dict[str, Any] = {"text": text}
        if attachments:
            body["attachments"] = attachments
        result: dict[str, Any] = await self._request(
            "POST", "/messages", params=params, json=body
        )
        return result

    async def send_notification(self, user_id: int, text: str, **kwargs: Any) -> dict[str, Any]:
        return await self.send_message(text, user_id=user_id, **kwargs)

    async def get_updates(
        self, marker: int | None, timeout: int = 30, types: list[str] | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"timeout": timeout, "limit": 100}
        if marker is not None:
            params["marker"] = marker
        if types:
            params["types"] = ",".join(types)
        result: dict[str, Any] = await self._request(
            "GET", "/updates", params=params, timeout=timeout + 10
        )
        return result

    async def create_subscription(
        self, url: str, update_types: list[str], secret: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"url": url, "update_types": update_types}
        if secret:
            body["secret"] = secret
        result: dict[str, Any] = await self._request("POST", "/subscriptions", json=body)
        return result

    async def delete_subscription(self, url: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request(
            "DELETE", "/subscriptions", params={"url": url}
        )
        return result
