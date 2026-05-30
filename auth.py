import os
from contextvars import ContextVar
from typing import Optional

current_user_id: ContextVar[str] = ContextVar("current_user_id", default="default")

_token_map: Optional[dict[str, str]] = None


def _load_tokens() -> dict[str, str]:
    raw = os.environ.get("ALLOWED_TOKENS", "")
    if not raw:
        return {}
    tokens: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            user_id, token = pair.split(":", 1)
            tokens[token.strip()] = user_id.strip()
    return tokens


def resolve_token(token: str) -> Optional[str]:
    global _token_map
    if _token_map is None:
        _token_map = _load_tokens()
    if not _token_map:
        return "default"
    return _token_map.get(token)


def get_user_id() -> str:
    return current_user_id.get()
