from __future__ import annotations

from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    discord_token: SecretStr = Field(validation_alias="DISCORD_TOKEN")
    discord_guild_id: int | None = Field(default=None, validation_alias="DISCORD_GUILD_ID")
    discord_owner_ids: list[int] = Field(default_factory=list, validation_alias="DISCORD_OWNER_IDS")

    torii_api_base_url: str = Field(
        default="https://lazer-api.shikkesora.com",
        validation_alias="TORII_API_BASE_URL",
    )
    torii_web_base_url: str = Field(
        default="https://lazer.shikkesora.com",
        validation_alias="TORII_WEB_BASE_URL",
    )
    torii_api_token: SecretStr | None = Field(default=None, validation_alias="TORII_API_TOKEN")
    torii_oauth_client_id: str | None = Field(default=None, validation_alias="TORII_OAUTH_CLIENT_ID")
    torii_oauth_client_secret: SecretStr | None = Field(default=None, validation_alias="TORII_OAUTH_CLIENT_SECRET")
    torii_oauth_username: str | None = Field(default=None, validation_alias="TORII_OAUTH_USERNAME")
    torii_oauth_password: SecretStr | None = Field(default=None, validation_alias="TORII_OAUTH_PASSWORD")
    torii_api_timeout_seconds: float = Field(default=15.0, validation_alias="TORII_API_TIMEOUT_SECONDS")

    bot_database_path: str = Field(default="./data/torii_bot.sqlite3", validation_alias="BOT_DATABASE_PATH")
    bot_log_level: str = Field(default="INFO", validation_alias="BOT_LOG_LEVEL")
    default_mode: str = Field(default="osu", validation_alias="DEFAULT_MODE")
    mod_alert_channel_id: int | None = Field(default=None, validation_alias="MOD_ALERT_CHANNEL_ID")
    mod_alert_token: SecretStr | None = Field(default=None, validation_alias="MOD_ALERT_TOKEN")
    mod_alert_poll_seconds: float = Field(default=5.0, validation_alias="MOD_ALERT_POLL_SECONDS")
    mod_alert_mention_here: bool = Field(default=True, validation_alias="MOD_ALERT_MENTION_HERE")

    economy_daily_min: int = Field(default=120, validation_alias="ECONOMY_DAILY_MIN")
    economy_daily_max: int = Field(default=260, validation_alias="ECONOMY_DAILY_MAX")
    economy_work_min: int = Field(default=30, validation_alias="ECONOMY_WORK_MIN")
    economy_work_max: int = Field(default=120, validation_alias="ECONOMY_WORK_MAX")
    economy_work_cooldown_minutes: int = Field(default=60, validation_alias="ECONOMY_WORK_COOLDOWN_MINUTES")

    @field_validator("discord_owner_ids", mode="before")
    @classmethod
    def _parse_owner_ids(cls, value: Any) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return [int(value)]

    @field_validator("default_mode")
    @classmethod
    def _validate_default_mode(cls, value: str) -> str:
        allowed = {"osu", "taiko", "fruits", "mania", "osurx", "osuap", "taikorx", "fruitsrx"}
        mode = value.lower().strip()
        if mode not in allowed:
            raise ValueError(f"DEFAULT_MODE must be one of: {', '.join(sorted(allowed))}")
        return mode

    @field_validator("torii_api_base_url", "torii_web_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")
