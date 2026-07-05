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

    # o!rdr render watch: postea los videos de replays renderizados (los que
    # el user compartio desde el cliente) en un canal. Cae al canal de
    # mod-alerts si no hay canal propio, como los otros watchers. Los threads
    # por video mantienen la conversacion fuera del feed principal.
    ordr_watch_channel_id: int | None = Field(default=None, validation_alias="ORDR_WATCH_CHANNEL_ID")
    # 4s: los renders de o!rdr son rapidos (<30s); hay que polear seguido para
    # agarrarlos EN CURSO y mostrar el progreso en vivo, no solo el final.
    ordr_watch_poll_seconds: float = Field(default=4.0, validation_alias="ORDR_WATCH_POLL_SECONDS")
    ordr_watch_create_threads: bool = Field(default=True, validation_alias="ORDR_WATCH_CREATE_THREADS")

    # Upstream-watch cog: polls ppy/osu master for breaking changes that
    # block a Torii rebase. Currently tracks the realm `schema_version`
    # constant (any bump means the on-disk DB is incompatible until we
    # write a migration). Channel falls back to the mod-alert channel
    # if a dedicated one isn't set — most servers want both alerts in
    # the same place.
    upstream_watch_channel_id: int | None = Field(default=None, validation_alias="UPSTREAM_WATCH_CHANNEL_ID")
    upstream_watch_interval_seconds: float = Field(default=21600.0, validation_alias="UPSTREAM_WATCH_INTERVAL_SECONDS")
    upstream_watch_mention_here: bool = Field(default=False, validation_alias="UPSTREAM_WATCH_MENTION_HERE")

    # daily-challenge watcher: chequeo diario 00:05 UTC. si el buffer de DC
    # agendados baja de min_buffer_days, pinguea el canal (cae al de mod-alerts
    # si no se setea uno propio) con @here.
    daily_challenge_watch_channel_id: int | None = Field(default=None, validation_alias="DAILY_CHALLENGE_WATCH_CHANNEL_ID")
    daily_challenge_watch_min_buffer_days: int = Field(default=2, validation_alias="DAILY_CHALLENGE_WATCH_MIN_BUFFER_DAYS")
    daily_challenge_watch_mention_here: bool = Field(default=True, validation_alias="DAILY_CHALLENGE_WATCH_MENTION_HERE")

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
