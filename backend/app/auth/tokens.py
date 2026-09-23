"""Stateless signed tokens: ``<base64url(payload)>.<base64url(hmac)>``.

Two kinds share one format:
- access token (``sub`` = user UUID) issued after MAX initData validation;
- link token (``mid`` = MAX user id) embedded in bot buttons, so a user opening the app
  from the chat is signed in without a Mini App registration.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from uuid import UUID


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class TokenSubject:
    user_id: UUID | None = None
    max_user_id: int | None = None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: dict[str, object], key: str) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(key.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def issue_token(user_id: UUID, key: str, ttl_seconds: int, now: float | None = None) -> str:
    issued = int(time.time() if now is None else now)
    return _sign({"sub": str(user_id), "exp": issued + ttl_seconds}, key)


def issue_link_token(
    max_user_id: int, key: str, ttl_seconds: int, now: float | None = None
) -> str:
    issued = int(time.time() if now is None else now)
    return _sign({"mid": max_user_id, "exp": issued + ttl_seconds}, key)


def verify_subject(token: str, key: str, now: float | None = None) -> TokenSubject:
    try:
        body, signature = token.split(".")
        expected = _b64(hmac.new(key.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise TokenError("invalid signature")
        data = json.loads(_unb64(body))
        if int(data["exp"]) < (time.time() if now is None else now):
            raise TokenError("token expired")
        if "sub" in data:
            return TokenSubject(user_id=UUID(data["sub"]))
        max_user_id = data["mid"]
        if not isinstance(max_user_id, int) or isinstance(max_user_id, bool):
            raise TokenError("malformed token")
        return TokenSubject(max_user_id=max_user_id)
    except TokenError:
        raise
    except (ValueError, KeyError, TypeError) as error:
        raise TokenError("malformed token") from error


def verify_token(token: str, key: str, now: float | None = None) -> UUID:
    subject = verify_subject(token, key, now)
    if subject.user_id is None:
        raise TokenError("not an access token")
    return subject.user_id
