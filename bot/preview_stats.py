"""Run score commands on a separate Discord application and test guild."""

import argparse

import discord
from discord.ext import commands
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from bot.cogs.osu import OsuStatsCog
from bot.config import Settings
from bot.database import BotDatabase
from bot.torii_api import ToriiApiClient


class PreviewSettings(Settings):
    model_config = SettingsConfigDict(env_file=".env.preview", env_file_encoding="utf-8", extra="ignore")
    discord_token: SecretStr = Field(validation_alias="DISCORD_PREVIEW_TOKEN")
    discord_guild_id: int = Field(gt=0, validation_alias="DISCORD_PREVIEW_GUILD_ID")


class PreviewTree(discord.app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id == self.client.settings.discord_guild_id:
            return True
        await interaction.response.send_message("This preview is limited to its test server.", ephemeral=True)
        return False


class StatsPreviewBot(commands.Bot):
    def __init__(self, settings: PreviewSettings):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, tree_cls=PreviewTree)
        self.settings = settings
        self.db = BotDatabase("./data/halo-preview.sqlite3")
        self.api = ToriiApiClient(
            base_url=settings.torii_api_base_url,
            web_base_url=settings.torii_web_base_url,
            token=settings.torii_api_token.get_secret_value() if settings.torii_api_token else None,
            oauth_client_id=settings.torii_oauth_client_id,
            oauth_client_secret=settings.torii_oauth_client_secret.get_secret_value() if settings.torii_oauth_client_secret else None,
            timeout=settings.torii_api_timeout_seconds,
        )

    async def setup_hook(self) -> None:
        await self.db.initialize()
        await self.add_cog(OsuStatsCog(self))
        guild = discord.Object(id=self.settings.discord_guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_message(self, message: discord.Message) -> None:
        if message.guild and message.guild.id == self.settings.discord_guild_id and not message.author.bot:
            await self.process_commands(message)

    async def close(self) -> None:
        await self.api.close()
        await self.db.close()
        await super().close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Validate settings without connecting to Discord.")
    args = parser.parse_args()
    settings = PreviewSettings()
    if args.check:
        print("Preview settings valid. No Discord connection was opened.")
        return
    StatsPreviewBot(settings).run(settings.discord_token.get_secret_value())


if __name__ == "__main__":
    main()

