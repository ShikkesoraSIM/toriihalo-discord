from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands


if TYPE_CHECKING:
    from bot.main import ToriiBot


class AdminCog(commands.Cog):
    def __init__(self, bot: ToriiBot) -> None:
        self.bot = bot

    def _is_owner(self, user_id: int) -> bool:
        return user_id in set(self.bot.settings.discord_owner_ids)

    @app_commands.command(name="sync", description="Sync slash commands (owner only).")
    @app_commands.describe(global_sync="Sync globally instead of only in configured guild.")
    async def sync(self, interaction: discord.Interaction, global_sync: bool = False) -> None:
        if not self._is_owner(interaction.user.id):
            await interaction.response.send_message("Owner only command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        if global_sync:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"Global sync complete: `{len(synced)}` commands.", ephemeral=True)
            return

        if self.bot.settings.discord_guild_id:
            guild = discord.Object(id=self.bot.settings.discord_guild_id)
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            await interaction.followup.send(
                f"Guild sync complete: `{len(synced)}` commands for `{self.bot.settings.discord_guild_id}`.",
                ephemeral=True,
            )
            return

        synced = await self.bot.tree.sync()
        await interaction.followup.send(
            f"No DISCORD_GUILD_ID configured. Fallback global sync: `{len(synced)}`.",
            ephemeral=True,
        )


async def setup(bot: ToriiBot) -> None:
    await bot.add_cog(AdminCog(bot))

