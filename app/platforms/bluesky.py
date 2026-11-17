from datetime import datetime, timezone

import httpx

from app.platforms.base import PlatformError, read_json, require_settings
from app.schemas import extract_urls

NAME = "Bluesky"
API_URL = "https://bsky.social/xrpc"


def build_link_facets(text: str) -> list[dict]:
    # Bluesky does not auto-link URLs in post text. Links need a facet whose
    # offsets are UTF-8 byte positions, not Python string indexes.
    facets = []
    search_from = 0
    for url in extract_urls(text):
        start = text.index(url, search_from)
        search_from = start + len(url)
        byte_start = len(text[:start].encode("utf-8"))
        byte_end = byte_start + len(url.encode("utf-8"))
        facets.append(
            {
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
            }
        )
    return facets


async def publish(client: httpx.AsyncClient, message: str) -> tuple[str | None, bool]:
    handle, app_password = require_settings("bluesky_handle", "bluesky_app_password")

    session = read_json(
        await client.post(
            f"{API_URL}/com.atproto.server.createSession",
            json={"identifier": handle, "password": app_password},
        )
    )
    access_jwt = session.get("accessJwt")
    did = session.get("did")
    if not access_jwt or not did:
        raise PlatformError("Unexpected response: session has no access token")

    record = {
        "$type": "app.bsky.feed.post",
        "text": message,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "facets": build_link_facets(message),
    }
    data = read_json(
        await client.post(
            f"{API_URL}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {access_jwt}"},
            json={"repo": did, "collection": "app.bsky.feed.post", "record": record},
        )
    )

    # The API returns an AT URI (at://<did>/app.bsky.feed.post/<rkey>); the web URL uses the rkey.
    uri = data.get("uri")
    if not uri:
        raise PlatformError("Unexpected response: no record URI returned")
    record_key = uri.rsplit("/", 1)[-1]
    profile = session.get("handle") or handle
    return f"https://bsky.app/profile/{profile}/post/{record_key}", True
