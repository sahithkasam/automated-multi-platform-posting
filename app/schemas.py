import re
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, ValidationError, field_validator
from pydantic_core import PydanticCustomError

MAX_MESSAGE_LENGTH = 200

# \S* (not \S+) so a bare "https://" is reported as an invalid URL rather than a missing one.
URL_PATTERN = re.compile(r"https?://\S*", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,;:!?)'\""

http_url_adapter = TypeAdapter(HttpUrl)


def extract_urls(text: str) -> list[str]:
    # Sentence punctuation right after a link ("visit https://example.com.") is not part of the URL.
    return [match.rstrip(TRAILING_PUNCTUATION) for match in URL_PATTERN.findall(text)]


class PostRequest(BaseModel):
    message: str = Field(
        description="Text to publish, up to 200 characters, with exactly one http(s) CTA link.",
        examples=["Check out our latest business platform. https://example.com"],
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise PydanticCustomError("empty_message", "Message cannot be empty")

        if len(value) > MAX_MESSAGE_LENGTH:
            raise PydanticCustomError(
                "message_too_long",
                "Message must be at most {limit} characters, got {length}",
                {"limit": MAX_MESSAGE_LENGTH, "length": len(value)},
            )

        urls = extract_urls(value)
        if not urls:
            raise PydanticCustomError(
                "missing_url", "Message must contain one CTA link starting with http:// or https://"
            )
        if len(urls) > 1:
            raise PydanticCustomError(
                "multiple_urls",
                "Message must contain exactly one URL, found {count}",
                {"count": len(urls)},
            )

        url = urls[0]
        try:
            parsed = http_url_adapter.validate_python(url)
        except ValidationError:
            raise PydanticCustomError("invalid_url", "Invalid URL: {url}", {"url": url})
        # HttpUrl accepts hosts like "https://promo", which cannot be a public CTA link.
        if not parsed.host or "." not in parsed.host:
            raise PydanticCustomError("invalid_url", "Invalid URL: {url}", {"url": url})

        return value


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: str | None = None
    public_access: bool = False
    date: str | None = Field(default=None, description="UTC date the platform confirmed the post")
    time: str | None = Field(default=None, description="UTC time the platform confirmed the post")
    error: str | None = None


class PostResponse(BaseModel):
    success: bool = Field(description="True if at least one platform published the message")
    results: list[PlatformResult]
