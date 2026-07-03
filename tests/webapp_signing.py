"""Builds validly-signed Telegram Mini App initData strings for tests (the inverse of api/auth.py)."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode


def sign_init_data(bot_token: str, user: dict, auth_date: int | None = None, **extra_fields: str) -> str:
    fields = {
        "user": json.dumps(user, separators=(",", ":")),
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        **extra_fields,
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": computed_hash})
