"""Stateless signed tokens: ``<base64url(payload)>.<base64url(hmac)>``.

Kinds share one format and are told apart by their payload key:
- access token (``sub`` = user UUID) issued after MAX initData validation;
- link token (``mid`` = MAX user id) embedded in bot buttons, so a user opening the app
  from the chat is signed in without a Mini App registration;
- calendar token (``cal`` = route step UUID) in a public .ics link. It grants no login;
- share token (``shr`` = user UUID, ``v`` = share version) for the read-only progress page
  a student sends to parents. Raising the user's share version revokes every such link.
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


def _verify(token: str, key: str, now: float | None) -> dict[str, object]:
    try:
        body, signature = token.split(".")
        expected = _b64(hmac.new(key.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise TokenError("invalid signature")
        data = json.loads(_unb64(body))
        if not isinstance(data, dict):
            raise TokenError("malformed token")
        if int(data["exp"]) < (time.time() if now is None else now):
            raise TokenError("token expired")
        return data
    except TokenError:
        raise
    except (ValueError, KeyError, TypeError) as error:
        raise TokenError("malformed token") from error


def verify_subject(token: str, key: str, now: float | None = None) -> TokenSubject:
    """Verify a login token (access or link). Calendar tokens are rejected."""
    data = _verify(token, key, now)
    try:
        if "sub" in data:
            return TokenSubject(user_id=UUID(str(data["sub"])))
        max_user_id = data["mid"]
    except (ValueError, KeyError) as error:
        raise TokenError("not a login token") from error
    if not isinstance(max_user_id, int) or isinstance(max_user_id, bool):
        raise TokenError("malformed token")
    return TokenSubject(max_user_id=max_user_id)


def issue_calendar_token(
    step_id: UUID, key: str, ttl_seconds: int, now: float | None = None
) -> str:
    issued = int(time.time() if now is None else now)
    return _sign({"cal": str(step_id), "exp": issued + ttl_seconds}, key)


def verify_calendar_token(token: str, key: str, now: float | None = None) -> UUID:
    data = _verify(token, key, now)
    try:
        return UUID(str(data["cal"]))
    except (ValueError, KeyError) as error:
        raise TokenError("not a calendar token") from error


def verify_token(token: str, key: str, now: float | None = None) -> UUID:
    subject = verify_subject(token, key, now)
    if subject.user_id is None:
        raise TokenError("not an access token")
    return subject.user_id


def issue_share_token(
    user_id: UUID, version: int, key: str, ttl_seconds: int, now: float | None = None
) -> str:
    issued = int(time.time() if now is None else now)
    return _sign({"shr": str(user_id), "v": version, "exp": issued + ttl_seconds}, key)


def verify_share_token(token: str, key: str, now: float | None = None) -> tuple[UUID, int]:
    data = _verify(token, key, now)
    try:
        version = data["v"]
        if not isinstance(version, int) or isinstance(version, bool):
            raise TokenError("malformed token")
        return UUID(str(data["shr"])), version
    except (ValueError, KeyError) as error:
        raise TokenError("not a share token") from error
