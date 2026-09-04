import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InvalidInitData(Exception):
    pass


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict:
    """Validates Telegram WebApp initData per Telegram's documented algorithm:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    Returns the decoded `user` field. Raises InvalidInitData on any failure."""
    if not bot_token:
        raise InvalidInitData("bot token not configured")

    parsed = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("missing hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidInitData("hash mismatch")

    auth_date = int(parsed.get("auth_date", 0))
    if time.time() - auth_date > max_age_seconds:
        raise InvalidInitData("init data expired")

    user_raw = parsed.get("user")
    if not user_raw:
        raise InvalidInitData("missing user field")

    try:
        return json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise InvalidInitData("malformed user field") from exc
