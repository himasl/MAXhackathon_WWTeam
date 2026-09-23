"""Validation of MAX Mini App launch parameters (``window.WebApp.initData``).

Algorithm from https://dev.max.ru/docs/webapps/validation:
secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
hash = hex(HMAC_SHA256(key=secret_key, msg="\\n".join(sorted("k=v" without hash))))
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    pass


@dataclass(frozen=True)
class MaxInitData:
    user_id: int
    first_name: str | None
    start_param: str | None
    auth_date: int


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign_init_data(params: dict[str, str], bot_token: str) -> str:
    """Return the hash for the given params. Used by tests and local tooling."""
    check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    return hmac.new(_secret_key(bot_token), check_string.encode(), hashlib.sha256).hexdigest()


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int,
    now: float | None = None,
) -> MaxInitData:
    raw = init_data.strip().lstrip("#")
    if raw.startswith("WebAppData="):
        # The URL fragment form wraps the payload once more.
        raw = dict(parse_qsl(raw)).get("WebAppData", "")
    pairs = parse_qsl(raw, keep_blank_values=True)
    hashes = [value for key, value in pairs if key == "hash"]
    if len(hashes) != 1:
        raise InitDataError("hash must be present exactly once")

    params = {key: value for key, value in pairs if key != "hash"}
    expected = sign_init_data(params, bot_token)
    if not hmac.compare_digest(expected, hashes[0].lower()):
        raise InitDataError("signature mismatch")

    try:
        auth_date = int(params["auth_date"])
    except (KeyError, ValueError) as error:
        raise InitDataError("auth_date is missing") from error
    current = time.time() if now is None else now
    if max_age_seconds > 0 and current - auth_date > max_age_seconds:
        raise InitDataError("init data expired")

    try:
        user = json.loads(params["user"])
        user_id = int(user["id"])
    except (KeyError, ValueError, TypeError) as error:
        raise InitDataError("user is missing") from error

    first_name = user.get("first_name")
    return MaxInitData(
        user_id=user_id,
        first_name=first_name if isinstance(first_name, str) else None,
        start_param=params.get("start_param") or None,
        auth_date=auth_date,
    )
