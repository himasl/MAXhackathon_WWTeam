"""Stateless signed access tokens: ``<base64url(payload)>.<base64url(hmac)>``."""

import base64
import hashlib
import hmac
import json
import time
from uuid import UUID


class TokenError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_token(user_id: UUID, key: str, ttl_seconds: int, now: float | None = None) -> str:
    issued = int(time.time() if now is None else now)
    payload = _b64(json.dumps({"sub": str(user_id), "exp": issued + ttl_seconds}).encode())
    signature = _b64(hmac.new(key.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify_token(token: str, key: str, now: float | None = None) -> UUID:
    try:
        payload, signature = token.split(".")
        expected = _b64(hmac.new(key.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise TokenError("invalid signature")
        data = json.loads(_unb64(payload))
        if int(data["exp"]) < (time.time() if now is None else now):
            raise TokenError("token expired")
        return UUID(data["sub"])
    except TokenError:
        raise
    except (ValueError, KeyError, TypeError) as error:
        raise TokenError("malformed token") from error
