import httpx

from app.platforms.base import PlatformError, read_json, require_settings

NAME = "Mastodon"


async def publish(client: httpx.AsyncClient, message: str) -> tuple[str | None, bool]:
    instance_url, token = require_settings("mastodon_instance_url", "mastodon_access_token")

    response = await client.post(
        f"{instance_url.rstrip('/')}/api/v1/statuses",
        headers={"Authorization": f"Bearer {token}"},
        data={"status": message, "visibility": "public"},
    )
    data = read_json(response)

    posted_url = data.get("url")
    if not posted_url:
        raise PlatformError("Unexpected response: no status URL returned")
    return posted_url, data.get("visibility") == "public"
