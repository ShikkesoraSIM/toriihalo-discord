from __future__ import annotations

import logging
from datetime import UTC
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.torii_api import ToriiApiError, ToriiApiUnauthorized
from bot.utils import clean_user_identifier


if TYPE_CHECKING:
    from bot.main import ToriiBot


logger = logging.getLogger(__name__)


class LinkingCog(commands.Cog):
    def __init__(self, bot: ToriiBot) -> None:
        self.bot = bot

    @app_commands.command(name="link", description="Link your Discord account with a Torii user.")
    @app_commands.describe(user="Torii username or user id")
    async def link(self, interaction: discord.Interaction, user: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        identifier = clean_user_identifier(user)
        if not identifier:
            await interaction.followup.send("Invalid username/id.", ephemeral=True)
            return

        try:
            torii_user = await self.bot.api.get_user(identifier)
        except ToriiApiUnauthorized as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except ToriiApiError as exc:
            await interaction.followup.send(f"Failed to fetch user: {exc}", ephemeral=True)
            return

        torii_user_id = int(torii_user["id"])
        username = str(torii_user.get("username") or identifier)
        await self.bot.db.link_account(interaction.user.id, torii_user_id, username)

        embed = discord.Embed(
            title="Account linked",
            description=f"`{interaction.user}` -> **{username}** (`{torii_user_id}`)",
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="unlink", description="Remove your Discord <-> Torii link.")
    async def unlink(self, interaction: discord.Interaction) -> None:
        removed = await self.bot.db.unlink_account(interaction.user.id)
        if removed:
            await interaction.response.send_message("Link removed.", ephemeral=True)
        else:
            await interaction.response.send_message("You don't have a linked account.", ephemeral=True)

    @app_commands.command(name="whoami", description="Show your linked Torii account.")
    async def whoami(self, interaction: discord.Interaction) -> None:
        link = await self.bot.db.get_linked_account(interaction.user.id)
        if not link:
            await interaction.response.send_message(
                "No linked account. Use `/link <username|id>` first.",
                ephemeral=True,
            )
            return

        linked_at = link.linked_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        embed = discord.Embed(
            title="Linked account",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Discord", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Torii", value=f"**{link.torii_username}** (`{link.torii_user_id}`)", inline=False)
        embed.set_footer(text=f"Linked at {linked_at}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: ToriiBot) -> None:
    await bot.add_cog(LinkingCog(bot))

