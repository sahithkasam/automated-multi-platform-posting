from typing import Any

import httpx
from pydantic import SecretStr

from app.config import settings


class PlatformError(Exception):
    """Failure with a message that is safe to return to the API client."""


def require_settings(*names: str) -> list[str]:
    values = []
    missing = []
    for name in names:
        value = getattr(settings, name)
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if not value:
            missing.append(name.upper())
        values.append(value)

    if missing:
        raise PlatformError(f"Missing credentials: {', '.join(missing)}")
    return values


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase

    if isinstance(body, dict):
        # Telegram uses "description"; GitHub, Bluesky and WordPress use "message"; Mastodon uses "error".
        for key in ("description", "message", "error"):
            if isinstance(body.get(key), str):
                return body[key][:200]
    return response.reason_phrase


def read_json(response: httpx.Response) -> dict[str, Any]:
    """Return the JSON body of a successful response, or raise PlatformError."""
    status = response.status_code
    detail = _error_detail(response) if not response.is_success else ""

    # GitHub reports exhausted rate limits as 403 with x-ratelimit-remaining: 0.
    is_rate_limited = status == 429 or (
        status == 403 and response.headers.get("x-ratelimit-remaining") == "0"
    )
    if is_rate_limited:
        retry_after = response.headers.get("retry-after")
        hint = f", retry after {retry_after}s" if retry_after else ""
        raise PlatformError(f"Rate limit exceeded{hint}: {detail}")
    if status == 401:
        raise PlatformError(f"Authentication failed: {detail}")
    if status == 403:
        raise PlatformError(f"Permission denied: {detail}")
    if not response.is_success:
        raise PlatformError(f"API error (HTTP {status}): {detail}")

    try:
        body = response.json()
    except ValueError:
        raise PlatformError(f"Unexpected non-JSON response (HTTP {status})")
    if not isinstance(body, dict):
        raise PlatformError(f"Unexpected response format (HTTP {status})")
    return body
