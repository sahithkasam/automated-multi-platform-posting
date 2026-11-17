import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.platforms import bluesky, github_gist, mastodon, telegram, wordpress
from app.platforms.base import PlatformError
from app.schemas import PlatformResult, PostResponse

logger = logging.getLogger(__name__)

PLATFORMS = [telegram, mastodon, bluesky, github_gist, wordpress]


async def publish_to_platform(client: httpx.AsyncClient, platform, message: str) -> PlatformResult:
    try:
        posted_url, public_access = await platform.publish(client, message)
    except PlatformError as exc:
        error = str(exc)
    except httpx.TimeoutException:
        # The request may have reached the platform, so a timeout is "unconfirmed", not "not posted".
        error = f"No response within {settings.request_timeout:g}s; the post may still have been published"
    except httpx.HTTPError as exc:
        # str(exc) can include the request URL, and the Telegram token is part of that URL.
        error = f"Network error: {type(exc).__name__}"
    except Exception:
        logger.exception("Unexpected error while posting to %s", platform.NAME)
        error = "Unexpected error while posting"
    else:
        now = datetime.now(timezone.utc)
        logger.info("%s: posted %s", platform.NAME, posted_url)
        return PlatformResult(
            platform=platform.NAME,
            status="success",
            posted_url=posted_url,
            public_access=public_access,
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M:%S"),
        )

    logger.warning("%s: failed - %s", platform.NAME, error)
    return PlatformResult(platform=platform.NAME, status="failed", error=error)


async def publish_to_all(message: str) -> PostResponse:
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        results = await asyncio.gather(
            *(publish_to_platform(client, platform, message) for platform in PLATFORMS)
        )

    return PostResponse(
        success=any(result.status == "success" for result in results),
        results=list(results),
    )
