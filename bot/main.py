from __future__ import annotations
import logging

import discord
from discord.ext import commands

from bot.config import Settings
from bot.database import BotDatabase
from bot.logging_setup import configure_logging
from bot.torii_api import ToriiApiClient


logger = logging.getLogger(__name__)

EXTENSIONS = (
    "bot.cogs.linking",
    "bot.cogs.osu",
    "bot.cogs.economy",
    "bot.cogs.fun",
    "bot.cogs.admin",
    "bot.cogs.mod_alerts",
    "bot.cogs.upstream_watch",
    "bot.cogs.daily_challenge_watch",
    "bot.cogs.ordr_watch",
    "bot.cogs.manual_output",
)


class ToriiBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        # Required to actually RECEIVE MESSAGE_CREATE events in guild
        # channels. intents.guilds covers guild lifecycle events
        # (joins/channels/roles) but NOT messages; without
        # guild_messages the bot's on_message never fires and prefix
        # commands silently no-op no matter how the prefix is set up.
        # Not a privileged intent — no portal config needed.
        intents.guild_messages = True
        # Privileged intent required for the bot to see the actual
        # text inside the MESSAGE_CREATE events it now receives.
        # Without this the event arrives but message.content is empty
        # in guilds (except when the bot is mentioned, per Discord's
        # mention-exception rule — but discord.py's command extension
        # still won't parse cleanly without it). Must also be toggled
        # ON in the Discord Developer Portal under "Privileged
        # Gateway Intents".
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = settings
        self.db = BotDatabase(settings.bot_database_path)
        self.api = ToriiApiClient(
            base_url=settings.torii_api_base_url,
            web_base_url=settings.torii_web_base_url,
            token=settings.torii_api_token.get_secret_value() if settings.torii_api_token else None,
            oauth_client_id=settings.torii_oauth_client_id,
            oauth_client_secret=(
                settings.torii_oauth_client_secret.get_secret_value()
                if settings.torii_oauth_client_secret
                else None
            ),
            oauth_username=settings.torii_oauth_username,
            oauth_password=(
                settings.torii_oauth_password.get_secret_value()
                if settings.torii_oauth_password
                else None
            ),
            timeout=settings.torii_api_timeout_seconds,
            mod_alert_token=settings.mod_alert_token.get_secret_value() if settings.mod_alert_token else None,
        )
        self.tree.on_error = self.on_tree_error

    async def setup_hook(self) -> None:
        await self.db.initialize()
        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logger.info("Loaded extension: %s", extension)

        if self.settings.discord_guild_id:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            try:
                synced = await self.tree.sync(guild=guild)
                logger.info("Synced %s commands to guild %s", len(synced), self.settings.discord_guild_id)
            except discord.Forbidden as exc:
                logger.warning(
                    "Guild sync failed for guild_id=%s (%s). Falling back to global sync.",
                    self.settings.discord_guild_id,
                    exc,
                )
                synced = await self.tree.sync()
                logger.info("Synced %s global commands (fallback)", len(synced))
        else:
            synced = await self.tree.sync()
            logger.info("Synced %s global commands", len(synced))

    async def on_ready(self) -> None:
        if self.user:
            logger.info("Bot ready as %s (%s)", self.user, self.user.id)

    # DEBUG: temporary instrumentation to trace prefix command dispatch
    # for the manual_output cog. Logs every incoming non-bot message
    # with its content preview + whether the bot was mentioned, plus
    # any prefix-command error. Once postdocs/postmenu are confirmed
    # working in prod this whole block can be deleted.
    async def on_message(self, message: discord.Message) -> None:
        if not message.author.bot:
            logger.info(
                "incoming msg author=%s channel=%s mentioned=%s content=%r",
                message.author,
                getattr(message.channel, "name", message.channel.id),
                self.user in message.mentions if self.user else False,
                message.content[:200],
            )
        await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        logger.exception("prefix command error in %s: %s", ctx.command, error)

    async def on_tree_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.exception("App command error: %s", error)
        message = f"Command failed: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def close(self) -> None:
        await self.api.close()
        await self.db.close()
        await super().close()


def main() -> None:
    configure_logging()
    settings = Settings()
    bot = ToriiBot(settings)
    token = settings.discord_token.get_secret_value()
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
