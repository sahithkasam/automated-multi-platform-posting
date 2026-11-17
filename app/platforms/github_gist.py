import httpx

from app.platforms.base import PlatformError, read_json, require_settings

NAME = "GitHub Gist"


async def publish(client: httpx.AsyncClient, message: str) -> tuple[str | None, bool]:
    (token,) = require_settings("github_token")

    response = await client.post(
        "https://api.github.com/gists",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "description": message,
            "public": True,
            "files": {"post.md": {"content": message}},
        },
    )
    data = read_json(response)

    posted_url = data.get("html_url")
    if not posted_url:
        raise PlatformError("Unexpected response: no html_url returned")
    return posted_url, data.get("public") is True
