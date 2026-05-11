from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils import format_number


if TYPE_CHECKING:
    from bot.main import ToriiBot


COINFLIP_CHOICES = [
    app_commands.Choice(name="heads", value="heads"),
    app_commands.Choice(name="tails", value="tails"),
]


class EconomyCog(commands.Cog):
    def __init__(self, bot: ToriiBot) -> None:
        self.bot = bot

    @app_commands.command(name="balance", description="Show your coin balance.")
    @app_commands.describe(member="Optional target member")
    async def balance(
        self,
        interaction: discord.Interaction,
        member: discord.Member | discord.User | None = None,
    ) -> None:
        target = member or interaction.user
        wallet = await self.bot.db.get_wallet(target.id)
        linked = await self.bot.db.get_linked_account(target.id)

        embed = discord.Embed(title="Torii Coins", color=discord.Color.gold())
        embed.add_field(name="User", value=target.mention, inline=False)
        embed.add_field(name="Balance", value=f"{format_number(wallet.coins)} coins", inline=True)
        embed.add_field(name="Daily Streak", value=str(wallet.daily_streak), inline=True)
        if linked:
            embed.set_footer(text=f"Linked Torii: {linked.torii_username}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily coins.")
    async def daily(self, interaction: discord.Interaction) -> None:
        try:
            reward, streak, next_claim, new_balance = await self.bot.db.claim_daily(
                interaction.user.id,
                self.bot.settings.economy_daily_min,
                self.bot.settings.economy_daily_max,
            )
        except ValueError as exc:
            text = str(exc)
            if text.startswith("cooldown:"):
                remaining = int(text.split(":", maxsplit=1)[1])
                wait = str(timedelta(seconds=remaining))
                await interaction.response.send_message(
                    f"You already claimed daily. Try again in `{wait}`.",
                    ephemeral=True,
                )
                return
            raise

        embed = discord.Embed(title="Daily claimed", color=discord.Color.green())
        embed.add_field(name="Reward", value=f"+{format_number(reward)} coins", inline=True)
        embed.add_field(name="Streak", value=str(streak), inline=True)
        embed.add_field(name="Balance", value=f"{format_number(new_balance)} coins", inline=True)
        embed.set_footer(text=f"Next claim at {next_claim.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Work once per cooldown for extra coins.")
    async def work(self, interaction: discord.Interaction) -> None:
        try:
            reward, next_work, new_balance = await self.bot.db.work(
                interaction.user.id,
                self.bot.settings.economy_work_min,
                self.bot.settings.economy_work_max,
                self.bot.settings.economy_work_cooldown_minutes,
            )
        except ValueError as exc:
            text = str(exc)
            if text.startswith("cooldown:"):
                remaining = int(text.split(":", maxsplit=1)[1])
                wait = str(timedelta(seconds=remaining))
                await interaction.response.send_message(
                    f"Work is on cooldown. Try again in `{wait}`.",
                    ephemeral=True,
                )
                return
            raise

        embed = discord.Embed(title="Work complete", color=discord.Color.blurple())
        embed.add_field(name="Earned", value=f"+{format_number(reward)} coins", inline=True)
        embed.add_field(name="Balance", value=f"{format_number(new_balance)} coins", inline=True)
        embed.set_footer(text=f"Next work at {next_work.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coinflip", description="Bet coins on heads/tails.")
    @app_commands.choices(side=COINFLIP_CHOICES)
    @app_commands.describe(amount="Bet amount", side="heads or tails")
    async def coinflip(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 1_000_000],
        side: str,
    ) -> None:
        result = random.choice(["heads", "tails"])
        won = result == side
        try:
            delta, new_balance = await self.bot.db.coinflip(interaction.user.id, amount, won)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        embed = discord.Embed(title="Coinflip", color=discord.Color.gold())
        embed.add_field(name="Your pick", value=side, inline=True)
        embed.add_field(name="Result", value=result, inline=True)
        embed.add_field(name="Delta", value=f"{delta:+,} coins", inline=True)
        embed.add_field(name="Balance", value=f"{format_number(new_balance)} coins", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pay", description="Transfer coins to another user.")
    @app_commands.describe(member="Target member", amount="Amount of coins")
    async def pay(
        self,
        interaction: discord.Interaction,
        member: discord.Member | discord.User,
        amount: app_commands.Range[int, 1, 1_000_000],
    ) -> None:
        try:
            from_balance, to_balance = await self.bot.db.pay(interaction.user.id, member.id, amount)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        embed = discord.Embed(title="Transfer complete", color=discord.Color.green())
        embed.add_field(name="From", value=f"{interaction.user.mention} ({format_number(from_balance)} left)", inline=False)
        embed.add_field(name="To", value=f"{member.mention} ({format_number(to_balance)} now)", inline=False)
        embed.add_field(name="Amount", value=f"{format_number(amount)} coins", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coins_top", description="Show top coin balances.")
    async def coins_top(self, interaction: discord.Interaction) -> None:
        top_rows = await self.bot.db.top_wallets(limit=10)
        embed = discord.Embed(title="Top Coins", color=discord.Color.orange())
        if not top_rows:
            embed.description = "No economy data yet."
            await interaction.response.send_message(embed=embed)
            return

        lines: list[str] = []
        for idx, (discord_user_id, coins, linked_name) in enumerate(top_rows, start=1):
            member_name = linked_name or f"<@{discord_user_id}>"
            lines.append(f"`#{idx:02}` {member_name} - **{format_number(coins)}**")
        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)


async def setup(bot: ToriiBot) -> None:
    await bot.add_cog(EconomyCog(bot))

