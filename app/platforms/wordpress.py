import html

import httpx

from app.platforms.base import PlatformError, read_json, require_settings
from app.schemas import extract_urls

NAME = "WordPress.com"
API_URL = "https://public-api.wordpress.com/rest/v1.1/sites"
MAX_TITLE_LENGTH = 80


def build_title(message: str) -> str:
    # WordPress posts need a title; use the message text without the link.
    text = message
    for url in extract_urls(message):
        text = text.replace(url, "")
    text = " ".join(text.split())

    if len(text) > MAX_TITLE_LENGTH:
        text = text[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0] + "..."
    return text or "Shared link"


def build_content(message: str) -> str:
    # Post content is HTML, so escape the text and turn the CTA URL into a real link.
    content = html.escape(message)
    for url in extract_urls(message):
        escaped_url = html.escape(url)
        content = content.replace(escaped_url, f'<a href="{escaped_url}">{escaped_url}</a>', 1)
    return content


async def publish(client: httpx.AsyncClient, message: str) -> tuple[str | None, bool]:
    site, token = require_settings("wordpress_site", "wordpress_access_token")
    site = site.removeprefix("https://").removeprefix("http://").strip("/")
    headers = {"Authorization": f"Bearer {token}"}

    # New WordPress.com sites start in "Coming soon" mode, where posts are not publicly
    # visible. Check first so a hidden post is never reported as public.
    site_info = read_json(await client.get(f"{API_URL}/{site}", headers=headers))
    if site_info.get("is_private") or site_info.get("is_coming_soon"):
        raise PlatformError("Site is private or in Coming Soon mode; launch it to make posts public")

    response = await client.post(
        f"{API_URL}/{site}/posts/new",
        headers=headers,
        data={"title": build_title(message), "content": build_content(message), "status": "publish"},
    )
    data = read_json(response)

    posted_url = data.get("URL")
    if not posted_url:
        raise PlatformError("Unexpected response: no post URL returned")
    return posted_url, data.get("status") == "publish"
