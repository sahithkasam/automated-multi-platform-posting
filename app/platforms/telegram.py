import httpx

from app.platforms.base import PlatformError, read_json, require_settings

NAME = "Telegram"


async def publish(client: httpx.AsyncClient, message: str) -> tuple[str | None, bool]:
    token, channel = require_settings("telegram_bot_token", "telegram_channel")
    channel = channel.removeprefix("@")

    response = await client.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": f"@{channel}", "text": message},
    )
    data = read_json(response)

    result = data.get("result") or {}
    message_id = result.get("message_id")
    if not data.get("ok") or not message_id:
        raise PlatformError("Unexpected response: no message_id returned")

    # Only channels with a public username have t.me links that open without logging in.
    username = (result.get("chat") or {}).get("username")
    if not username:
        return None, False
    return f"https://t.me/{username}/{message_id}", True
