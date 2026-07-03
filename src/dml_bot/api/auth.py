"""Validates Telegram Mini App `initData` per Telegram's documented HMAC-SHA256 scheme.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60


class InvalidInitData(Exception):
    pass


@dataclass
class TelegramWebAppUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None


def _compute_hash(data_check_string: str, bot_token: str) -> str:
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def validate_init_data(init_data: str, bot_token: str, now: float | None = None) -> TelegramWebAppUser:
    if not init_data:
        raise InvalidInitData("empty initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("missing hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    expected_hash = _compute_hash(data_check_string, bot_token)
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InvalidInitData("signature mismatch")

    auth_date = pairs.get("auth_date")
    if not auth_date:
        raise InvalidInitData("missing auth_date")
    now = time.time() if now is None else now
    if now - float(auth_date) > MAX_INIT_DATA_AGE_SECONDS:
        raise InvalidInitData("initData expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise InvalidInitData("missing user")
    try:
        user_dict = json.loads(user_raw)
        user_id = int(user_dict["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidInitData("malformed user field") from exc

    return TelegramWebAppUser(
        id=user_id,
        first_name=user_dict.get("first_name", ""),
        last_name=user_dict.get("last_name"),
        username=user_dict.get("username"),
    )
