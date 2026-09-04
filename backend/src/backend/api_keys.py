import hashlib
import secrets

_KEY_PREFIX = "crm_"


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (plaintext_key, key_hash, key_prefix). Only key_hash is stored —
    the plaintext key is shown to the caller once, at creation time."""
    key = _KEY_PREFIX + secrets.token_urlsafe(32)
    return key, hash_api_key(key), key[: len(_KEY_PREFIX) + 8]
