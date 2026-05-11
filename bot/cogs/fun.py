from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord import app_commands


if TYPE_CHECKING:
    from bot.main import ToriiBot


def owoify(text: str) -> str:
    out = text
    out = re.sub(r"[rl]", "w", out)
    out = re.sub(r"[RL]", "W", out)
    out = re.sub(r"n([aeiou])", r"ny\1", out, flags=re.IGNORECASE)
    return out


class FunCog(commands.Cog):
    def __init__(self, bot: ToriiBot) -> None:
        self.bot = bot

    @app_commands.command(name="owoify", description="Owoify text.")
    @app_commands.describe(text="Text to owoify")
    async def owoify_cmd(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.send_message(owoify(text))

    @app_commands.command(name="ping", description="Bot health check.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! `{latency_ms}ms`")


async def setup(bot: ToriiBot) -> None:
    await bot.add_cog(FunCog(bot))

