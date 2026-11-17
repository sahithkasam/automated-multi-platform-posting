import logging

from fastapi import FastAPI

from app.schemas import PostRequest, PostResponse
from app.services.posting_service import publish_to_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs every request URL at INFO level, and the Telegram bot token is part of that URL.
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(
    title="Automated Posting API",
    version="1.0.0",
    description="Publishes a short message with one CTA link to Telegram, Mastodon, "
    "Bluesky, GitHub Gist and WordPress.com.",
)


@app.post("/posting", response_model=PostResponse, summary="Publish a message to all configured platforms")
async def create_post(request: PostRequest) -> PostResponse:
    return await publish_to_all(request.message)
