# Automated Multi-Platform Posting System

A FastAPI service that takes a short message with one CTA link and publishes it to five platforms through their official APIs:

- Telegram (public channel)
- Mastodon
- Bluesky
- GitHub Gist
- WordPress.com

The client sends only the message. The service posts to every platform concurrently and returns a result per platform.

## Technology stack

- Python 3.12
- FastAPI and Uvicorn
- Pydantic v2 and pydantic-settings
- HTTPX (async client)
- pytest and respx for tests

## Project structure

```text
app/
  main.py                  FastAPI app and the POST /posting route
  config.py                Settings loaded from environment variables / .env
  schemas.py               Request validation and response models
  platforms/
    base.py                Shared error type, credential check and response handling
    telegram.py
    mastodon.py
    bluesky.py
    github_gist.py
    wordpress.py
  services/
    posting_service.py     Runs all platforms concurrently and builds the response
tests/
  test_posting.py
```

Each platform module exposes `NAME` and `async publish(client, message)`, which returns `(posted_url, public_access)` or raises `PlatformError`. Adding a platform means adding a module and listing it in `PLATFORMS` in `posting_service.py`.

## Installation

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with the credentials described below. A platform with missing credentials is reported as `failed` with the names of the missing variables; the other platforms still post.

## Environment variables

| Variable | Description |
|---|---|
| `REQUEST_TIMEOUT` | Seconds to wait for each API call (default 10) |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHANNEL` | Public channel username, with or without `@` |
| `MASTODON_INSTANCE_URL` | Instance base URL (default `https://mastodon.social`) |
| `MASTODON_ACCESS_TOKEN` | Application access token with `write:statuses` |
| `BLUESKY_HANDLE` | Account handle, e.g. `name.bsky.social` |
| `BLUESKY_APP_PASSWORD` | App password, not the account password |
| `GITHUB_TOKEN` | Fine-grained token with Gists read/write |
| `WORDPRESS_SITE` | Site address, e.g. `yoursite.wordpress.com` |
| `WORDPRESS_ACCESS_TOKEN` | OAuth2 access token for the WordPress.com account |

## Obtaining credentials

**Telegram**
1. Message [@BotFather](https://t.me/BotFather), send `/newbot` and copy the token.
2. Create a channel, set it to Public and choose a username.
3. Channel settings > Administrators > add the bot with the "Post Messages" permission.
4. Set `TELEGRAM_CHANNEL` to the channel username.

**Mastodon**
1. Create an account on mastodon.social and confirm the email.
2. Profile settings > tick "This is an automated account" (instance rules expect bots to be flagged).
3. Preferences > Development > New application. Select only the `write:statuses` scope, save, and copy "Your access token".
4. If you change scopes later, use "Regenerate access token"; existing tokens keep their old scopes.

**Bluesky**
1. Create an account at bsky.app and verify the email.
2. Settings > Privacy and security > App passwords > Add app password.

**GitHub Gist**
1. Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token.
2. Under Account permissions, set "Gists" to "Read and write". No repository access is needed.

**WordPress.com**
1. Sign up with email and password and create a free `*.wordpress.com` site.
2. Make the site public: Settings > General > Site Visibility > Public (new sites start in "Coming soon" mode).
3. Register an app at https://developer.wordpress.com/apps/new/ (type Web, redirect URL `http://localhost:4000`). The app page shows the Client ID and Client Secret.
4. Exchange them once for a long-lived access token using the password grant, which WordPress.com allows for the app owner's own account:

   ```bash
   curl -X POST https://public-api.wordpress.com/oauth2/token \
     -d client_id=CLIENT_ID \
     -d client_secret=CLIENT_SECRET \
     -d grant_type=password \
     -d username=WORDPRESS_USERNAME \
     -d password=WORDPRESS_PASSWORD
   ```

   Put `access_token` from the response in `WORDPRESS_ACCESS_TOKEN`. The password is only needed for this one call and is not stored. With two-step verification enabled, use an application password.

## Running the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Swagger UI: http://localhost:4000/docs

## API

`POST /posting`

Validation rules:

- `message` is required and cannot be empty or whitespace.
- At most 200 characters (after trimming surrounding whitespace).
- Exactly one `http://` or `https://` URL. Trailing sentence punctuation such as `.` or `)` is not treated as part of the URL.
- The URL must parse as a valid HTTP URL and have a domain with a dot, so `https://localhost` is rejected.

Request:

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{"message": "Automated multi-platform posting with Python and FastAPI: one request, five platforms. Docs: https://fastapi.tiangolo.com/tutorial/"}'
```

Response from a live run on 17 Nov 2026 (`200 OK`):

```json
{
  "success": true,
  "results": [
    {
      "platform": "Telegram",
      "status": "success",
      "posted_url": "https://t.me/dexora_posting_test/5",
      "public_access": true,
      "date": "2026-11-17",
      "time": "13:05:39",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "success",
      "posted_url": "https://mastodon.social/@sahith02/117631925591757421",
      "public_access": true,
      "date": "2026-11-17",
      "time": "13:05:39",
      "error": null
    },
    {
      "platform": "Bluesky",
      "status": "success",
      "posted_url": "https://bsky.app/profile/sahith02.bsky.social/post/3n2j4am4l4725",
      "public_access": true,
      "date": "2026-11-17",
      "time": "13:05:40",
      "error": null
    },
    {
      "platform": "GitHub Gist",
      "status": "success",
      "posted_url": "https://gist.github.com/sahithkasam/dbb5062bed3b9bfa855891111589b282",
      "public_access": true,
      "date": "2026-11-17",
      "time": "13:05:40",
      "error": null
    },
    {
      "platform": "WordPress.com",
      "status": "success",
      "posted_url": "https://dexorapostingtest.wordpress.com/2026/11/17/automated-multi-platform-posting-with-python-and-fastapi-one-request-five/",
      "public_access": true,
      "date": "2026-11-17",
      "time": "13:05:44",
      "error": null
    }
  ]
}
```

Server log for the same request (times are local, IST):

```text
INFO app.services.posting_service: Mastodon: posted https://mastodon.social/@sahith02/117631925591757421
INFO app.services.posting_service: Telegram: posted https://t.me/dexora_posting_test/5
INFO app.services.posting_service: Bluesky: posted https://bsky.app/profile/sahith02.bsky.social/post/3n2j4am4l4725
INFO app.services.posting_service: GitHub Gist: posted https://gist.github.com/sahithkasam/dbb5062bed3b9bfa855891111589b282
INFO app.services.posting_service: WordPress.com: posted https://dexorapostingtest.wordpress.com/2026/11/17/automated-multi-platform-posting-with-python-and-fastapi-one-request-five/
INFO:     127.0.0.1:52386 - "POST /posting HTTP/1.1" 200 OK
```

The log order shows the platforms ran concurrently: each line is written when that platform responds, not in list order.

A partial failure from an earlier live run, when the Mastodon token had been revoked (other platforms still posted and `success` stayed `true`):

```json
{
  "platform": "Mastodon",
  "status": "failed",
  "posted_url": null,
  "public_access": false,
  "date": null,
  "time": null,
  "error": "Authentication failed: The access token is invalid"
}
```

Validation error (`422`):

```json
{
  "detail": [
    {
      "type": "multiple_urls",
      "loc": ["body", "message"],
      "msg": "Message must contain exactly one URL, found 2",
      "input": "two https://a.com https://b.com",
      "ctx": {"count": 2}
    }
  ]
}
```

### Response fields

- `success` is `true` when at least one platform published the message, matching the sample in the assignment. Check `results` for per-platform status. A valid request always returns `200`, even when every platform fails, because the request itself was processed; failures are reported per platform.
- `status` is `success` only after the platform API returned a confirmed post. A `2xx` response without the expected post URL or ID is reported as `failed`.
- `posted_url` is built only from data in the API response, never guessed.
- `public_access` is `true` when the post can be opened without logging in, taken from the API response where the platform reports it (Mastodon `visibility`, Gist `public`, WordPress `status`, Telegram channel username). WordPress posting is refused if the site is private or in "Coming soon" mode.
- `date` and `time` are UTC, recorded when the platform confirmed the post. They are `null` for failed posts.
- `error` is `null` on success, otherwise a short reason: missing credentials, authentication failure, permission denied, rate limit (with `Retry-After` if provided), timeout, network error or unexpected response.

### Error handling

Each platform runs in its own `try` block inside `asyncio.gather`, so an exception in one never cancels the others. Error messages never include credentials. HTTPX exception text is not returned because it can contain the request URL, and the Telegram API puts the bot token in the URL. For the same reason the `httpx` logger is set to `WARNING`.

Rate limits are reported, not retried. Retrying inside the request would hold the HTTP response open for the full `Retry-After` period, which can be minutes on some platforms.

## Testing

```bash
pytest -v
```

`tests/test_posting.py` contains automated tests only. Every external HTTP call is mocked with respx and credentials are replaced with fake values, so the tests make no network calls and do not need a `.env` file. They cover:

- validation: missing field, empty and whitespace-only messages, over 200 characters, exactly 200 characters, no URL, multiple URLs, invalid URLs
- all platforms succeeding, partial failure, all platforms failing
- missing credentials (no request is sent for that platform)
- timeout, network error (and that the token is not leaked), rate limit, unexpected API response
- WordPress site in "Coming soon" mode is not posted to; WordPress content is HTML-escaped
- Bluesky link facet byte offsets with non-ASCII text

Real publishing was verified separately by running the server with real credentials, calling `POST /posting`, and opening every returned URL in a logged-out session. Those posts are public, so they are not part of the automated test suite.

## Platform API notes

| Platform | Endpoint | Auth | Posted URL source | Limits |
|---|---|---|---|---|
| Telegram | `POST /bot<token>/sendMessage` | Bot token in URL | `t.me/<chat.username>/<message_id>` | About 20 messages/minute per channel; 429 includes `retry_after` |
| Mastodon | `POST /api/v1/statuses` | Bearer token, `write:statuses` | `url` | 500 characters; 300 posts per 3 hours per account |
| Bluesky | `com.atproto.server.createSession`, then `com.atproto.repo.createRecord` | App password exchanged for a JWT | `bsky.app/profile/<handle>/post/<rkey>` from the returned `at://` URI | 300 graphemes; createSession is limited to 30 per 5 minutes |
| GitHub Gist | `POST /gists` | Bearer token | `html_url` | 5,000 requests/hour plus secondary limits on content creation |
| WordPress.com | `GET /rest/v1.1/sites/<site>`, then `POST /rest/v1.1/sites/<site>/posts/new` | OAuth2 bearer token | `URL` | Requires a title; content is HTML |

Platform-specific details:

- Bluesky does not auto-link URLs. A link needs a "facet" with UTF-8 byte offsets, so the offsets are computed on the encoded text rather than with Python string indexes.
- WordPress content is HTML, so the message is escaped and the CTA URL is wrapped in an `<a>` tag. The title is the message text without the link.

### Platforms considered and dropped

- **DEV Community** (Forem API) was in the first version. Posting worked and the API returned published article URLs, but shortly after, DEV's moderation hid the new account and its articles (404) and the API key started returning 401. Short link-only articles from a new account appear to trigger its spam filter.
- **Telegraph** (telegra.ph) has a simple official API, but the domain is blocked by Indian ISPs, so the posts would not be reachable for many readers.
- **Hashnode** moved its GraphQL API to a paid Pro plan in May 2026.
- **X, Reddit, LinkedIn, Threads**: paid write access, API approval, or an OAuth app review that does not fit the scope of this assignment.
- **Discord and Slack webhooks** were not used because their messages are not publicly accessible.

## Known limitations

- A new Bluesky session is created on every request. This is simple and well within the limit for manual use, but frequent posting would need session reuse.
- No automatic retries. A failed platform has to be retried by sending the request again, which also re-posts to the platforms that succeeded.
- No duplicate detection across requests.
- A timeout is reported as `failed` because the post could not be confirmed, but the platform may still have published it. This happened once with Telegram during live testing: the message appeared in the channel after the 10 second timeout.
- A confirmed post can still be removed later by platform moderation, as happened with DEV. The API response only reflects the state at publish time.

## References

- Telegram Bot API: https://core.telegram.org/bots/api#sendmessage
- Mastodon statuses: https://docs.joinmastodon.org/methods/statuses/#create
- Mastodon rate limits: https://docs.joinmastodon.org/api/rate-limits/
- Bluesky creating a post: https://docs.bsky.app/docs/tutorials/creating-a-post
- Bluesky rate limits: https://docs.bsky.app/docs/advanced-guides/rate-limits
- GitHub create a gist: https://docs.github.com/en/rest/gists/gists#create-a-gist
- GitHub rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- WordPress.com OAuth2: https://developer.wordpress.com/docs/api/oauth2/
- WordPress.com create a post: https://developer.wordpress.com/docs/api/1.1/post/sites/%24site/posts/new/
