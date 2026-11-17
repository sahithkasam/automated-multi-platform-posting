"""Automated tests. Every external API call is mocked with respx; nothing is posted for real."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.platforms.bluesky import build_link_facets
from app.platforms.wordpress import build_content

client = TestClient(app)

VALID_MESSAGE = "Check out our latest business platform. https://example.com"

FAKE_TELEGRAM_TOKEN = "123:fake-telegram-token"
TELEGRAM_URL = f"https://api.telegram.org/bot{FAKE_TELEGRAM_TOKEN}/sendMessage"
MASTODON_URL = "https://mastodon.test/api/v1/statuses"
BLUESKY_SESSION_URL = "https://bsky.social/xrpc/com.atproto.server.createSession"
BLUESKY_RECORD_URL = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
GIST_URL = "https://api.github.com/gists"
WORDPRESS_SITE_URL = "https://public-api.wordpress.com/rest/v1.1/sites/tester.wordpress.com"
WORDPRESS_POST_URL = f"{WORDPRESS_SITE_URL}/posts/new"


@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    fake_values = {
        "request_timeout": 5.0,
        "telegram_bot_token": SecretStr(FAKE_TELEGRAM_TOKEN),
        "telegram_channel": "test_channel",
        "mastodon_instance_url": "https://mastodon.test",
        "mastodon_access_token": SecretStr("fake-mastodon-token"),
        "bluesky_handle": "tester.bsky.social",
        "bluesky_app_password": SecretStr("fake-app-password"),
        "github_token": SecretStr("fake-github-token"),
        "wordpress_site": "https://tester.wordpress.com/",
        "wordpress_access_token": SecretStr("fake-wordpress-token"),
    }
    for name, value in fake_values.items():
        monkeypatch.setattr(settings, name, value)


@pytest.fixture
def api_mock():
    with respx.mock(assert_all_called=False) as router:
        router.post(TELEGRAM_URL, name="telegram").respond(
            200, json={"ok": True, "result": {"message_id": 42, "chat": {"username": "test_channel"}}}
        )
        router.post(MASTODON_URL, name="mastodon").respond(
            200, json={"url": "https://mastodon.test/@tester/111", "visibility": "public"}
        )
        router.post(BLUESKY_SESSION_URL, name="bluesky_session").respond(
            200, json={"accessJwt": "jwt", "did": "did:plc:abc", "handle": "tester.bsky.social"}
        )
        router.post(BLUESKY_RECORD_URL, name="bluesky_record").respond(
            200, json={"uri": "at://did:plc:abc/app.bsky.feed.post/3kxyz", "cid": "cid"}
        )
        router.post(GIST_URL, name="github").respond(
            201, json={"html_url": "https://gist.github.com/tester/abc123", "public": True}
        )
        router.get(WORDPRESS_SITE_URL, name="wordpress_site").respond(
            200, json={"is_private": False, "is_coming_soon": False}
        )
        router.post(WORDPRESS_POST_URL, name="wordpress").respond(
            200, json={"URL": "https://tester.wordpress.com/2026/11/17/check-out/", "status": "publish"}
        )
        yield router


def post_message(message):
    return client.post("/posting", json={"message": message})


def results_by_platform(response):
    return {result["platform"]: result for result in response.json()["results"]}


# Input validation


def error_message(response):
    assert response.status_code == 422
    return response.json()["detail"][0]["msg"]


def test_missing_message_field():
    response = client.post("/posting", json={})
    assert error_message(response) == "Field required"


@pytest.mark.parametrize("message", ["", "    "])
def test_empty_message(message):
    assert error_message(post_message(message)) == "Message cannot be empty"


def test_message_over_200_characters():
    message = "a" * 190 + " https://example.com"
    assert error_message(post_message(message)) == "Message must be at most 200 characters, got 210"


def test_message_of_exactly_200_characters_is_accepted(api_mock):
    message = "a" * 180 + " https://example.com"
    assert len(message) == 200
    assert post_message(message).status_code == 200


def test_message_without_url():
    assert error_message(post_message("No link in this message, only www.example.com")) == (
        "Message must contain one CTA link starting with http:// or https://"
    )


def test_message_with_multiple_urls():
    message = "Two links https://example.com and https://example.org"
    assert error_message(post_message(message)) == "Message must contain exactly one URL, found 2"


@pytest.mark.parametrize("url", ["https://", "https://localhost", "https://example.com:99999"])
def test_invalid_url(url):
    assert error_message(post_message(f"Visit {url}")).startswith("Invalid URL")


def test_trailing_punctuation_is_not_part_of_url(api_mock):
    assert post_message("Visit our site https://example.com.").status_code == 200


# Publishing


def test_all_platforms_succeed(api_mock):
    response = post_message(VALID_MESSAGE)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    results = results_by_platform(response)
    assert set(results) == {"Telegram", "Mastodon", "Bluesky", "GitHub Gist", "WordPress.com"}
    assert results["Telegram"]["posted_url"] == "https://t.me/test_channel/42"
    assert results["Bluesky"]["posted_url"] == "https://bsky.app/profile/tester.bsky.social/post/3kxyz"
    for result in results.values():
        assert result["status"] == "success"
        assert result["public_access"] is True
        assert result["error"] is None
        assert result["date"] and result["time"]


def test_partial_failure_does_not_stop_other_platforms(api_mock):
    api_mock["mastodon"].respond(401, json={"error": "The access token is invalid"})

    response = post_message(VALID_MESSAGE)

    body = response.json()
    assert body["success"] is True
    results = results_by_platform(response)
    assert results["Mastodon"] == {
        "platform": "Mastodon",
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": "Authentication failed: The access token is invalid",
    }
    succeeded = [name for name, result in results.items() if result["status"] == "success"]
    assert len(succeeded) == 4


def test_all_platforms_fail(api_mock):
    for name in ("telegram", "mastodon", "bluesky_session", "github", "wordpress_site"):
        api_mock[name].respond(503, text="Service Unavailable")

    response = post_message(VALID_MESSAGE)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    for result in body["results"]:
        assert result["status"] == "failed"
        assert result["error"] == "API error (HTTP 503): Service Unavailable"


def test_missing_credentials_skip_the_api_call(api_mock, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    monkeypatch.setattr(settings, "wordpress_access_token", SecretStr(""))

    results = results_by_platform(post_message(VALID_MESSAGE))

    assert results["Telegram"]["error"] == "Missing credentials: TELEGRAM_BOT_TOKEN"
    assert results["WordPress.com"]["error"] == "Missing credentials: WORDPRESS_ACCESS_TOKEN"
    assert not api_mock["telegram"].called
    assert not api_mock["wordpress_site"].called
    assert results["Mastodon"]["status"] == "success"


def test_timeout_is_reported(api_mock):
    api_mock["github"].side_effect = httpx.ReadTimeout("timed out")

    results = results_by_platform(post_message(VALID_MESSAGE))

    assert results["GitHub Gist"]["status"] == "failed"
    assert results["GitHub Gist"]["error"] == "No response within 5s; the post may still have been published"
    assert results["Telegram"]["status"] == "success"


def test_network_error_does_not_leak_token(api_mock):
    api_mock["telegram"].side_effect = httpx.ConnectError(f"cannot reach {TELEGRAM_URL}")

    response = post_message(VALID_MESSAGE)

    assert results_by_platform(response)["Telegram"]["error"] == "Network error: ConnectError"
    assert FAKE_TELEGRAM_TOKEN not in response.text


def test_rate_limit_is_reported(api_mock):
    api_mock["wordpress"].respond(429, headers={"Retry-After": "30"}, json={"error": "Rate limit reached"})

    result = results_by_platform(post_message(VALID_MESSAGE))["WordPress.com"]

    assert result["error"] == "Rate limit exceeded, retry after 30s: Rate limit reached"


def test_unexpected_response_is_not_reported_as_success(api_mock):
    api_mock["github"].respond(201, json={"id": "abc123"})
    api_mock["mastodon"].respond(200, text="<html>maintenance</html>")

    results = results_by_platform(post_message(VALID_MESSAGE))

    assert results["GitHub Gist"]["error"] == "Unexpected response: no html_url returned"
    assert results["Mastodon"]["error"] == "Unexpected non-JSON response (HTTP 200)"
    assert results["GitHub Gist"]["posted_url"] is None


def test_bluesky_link_facet_uses_byte_offsets():
    text = "Café ☕ https://example.com"
    facet = build_link_facets(text)[0]

    start, end = facet["index"]["byteStart"], facet["index"]["byteEnd"]
    assert text.encode("utf-8")[start:end] == b"https://example.com"
    assert facet["features"][0]["uri"] == "https://example.com"


def test_wordpress_site_in_coming_soon_mode_is_not_posted_to(api_mock):
    api_mock["wordpress_site"].respond(200, json={"is_private": False, "is_coming_soon": True})

    result = results_by_platform(post_message(VALID_MESSAGE))["WordPress.com"]

    assert result["status"] == "failed"
    assert result["error"].startswith("Site is private or in Coming Soon mode")
    assert not api_mock["wordpress"].called


def test_wordpress_content_escapes_html_and_links_the_url():
    content = build_content("Tips & <b>tricks</b> https://example.com/?a=1&b=2")

    assert "<b>" not in content
    assert content == (
        "Tips &amp; &lt;b&gt;tricks&lt;/b&gt; "
        '<a href="https://example.com/?a=1&amp;b=2">https://example.com/?a=1&amp;b=2</a>'
    )
