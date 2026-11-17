from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    request_timeout: float = 10.0

    telegram_bot_token: SecretStr | None = None
    telegram_channel: str | None = None

    mastodon_instance_url: str = "https://mastodon.social"
    mastodon_access_token: SecretStr | None = None

    bluesky_handle: str | None = None
    bluesky_app_password: SecretStr | None = None

    github_token: SecretStr | None = None

    wordpress_site: str | None = None
    wordpress_access_token: SecretStr | None = None


settings = Settings()
