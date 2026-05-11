from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands, tasks

from bot.torii_api import ToriiApiError, ToriiApiUnauthorized


logger = logging.getLogger(__name__)

SEVERITY_COLOURS = {
    "info": discord.Color.blue(),
    "warning": discord.Color.orange(),
    "critical": discord.Color.red(),
}


class ModAlertsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.poll_mod_alerts.start()

    def cog_unload(self) -> None:
        self.poll_mod_alerts.cancel()

    async def _resolve_channel(self) -> discord.TextChannel | None:
        channel_id = self.bot.settings.mod_alert_channel_id
        if not channel_id:
            return None

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.DiscordException as exc:
                logger.warning("Failed to fetch moderation alert channel %s: %s", channel_id, exc)
                return None

        if isinstance(channel, discord.TextChannel):
            return channel
        logger.warning("Configured moderation alert channel %s is not a text channel.", channel_id)
        return None

    @tasks.loop(seconds=5.0)
    async def poll_mod_alerts(self) -> None:
        poll_seconds = max(2.0, float(self.bot.settings.mod_alert_poll_seconds))
        if abs(self.poll_mod_alerts.seconds - poll_seconds) > 0.001:
            self.poll_mod_alerts.change_interval(seconds=poll_seconds)

        channel = await self._resolve_channel()
        if channel is None or not self.bot.settings.mod_alert_token:
            return

        try:
            alerts = await self.bot.api.get_pending_mod_alerts(limit=10)
        except ToriiApiUnauthorized as exc:
            logger.warning("Mod alert polling unauthorized: %s", exc)
            return
        except ToriiApiError as exc:
            logger.warning("Mod alert polling failed: %s", exc)
            return
        except Exception as exc:
            logger.exception("Unexpected error while polling mod alerts: %s", exc)
            return

        for alert in alerts:
            try:
                embed = self._build_embed(alert)
                severity = str(alert.get("severity", "warning")).lower()
                mention = "@here" if self.bot.settings.mod_alert_mention_here and severity == "critical" else None
                await channel.send(
                    content=mention,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(everyone=True),
                )
                await self.bot.api.mark_mod_alert_dispatched(int(alert["id"]))
            except Exception as exc:
                logger.exception("Failed to post moderation alert %s: %s", alert.get("id"), exc)
                break

    @poll_mod_alerts.before_loop
    async def before_poll_mod_alerts(self) -> None:
        await self.bot.wait_until_ready()

    def _build_embed(self, alert: dict[str, Any]) -> discord.Embed:
        severity = str(alert.get("severity", "warning")).lower()
        metadata = alert.get("metadata") or {}
        embed = discord.Embed(
            title=str(alert.get("title") or "Suspicious activity detected"),
            description=str(alert.get("body") or ""),
            color=SEVERITY_COLOURS.get(severity, discord.Color.orange()),
        )
        embed.set_footer(text=f"{alert.get('kind', 'alert')} - severity: {severity}")

        username = metadata.get("username")
        user_id = metadata.get("user_id")
        if username or user_id:
            user_value = f"[{username} #{user_id}]({self.bot.api.user_url(user_id)})" if user_id else str(username)
            embed.add_field(name="User", value=user_value, inline=True)

        beatmap_name = metadata.get("beatmap_name")
        beatmap_id = metadata.get("beatmap_id")
        if beatmap_name or beatmap_id:
            beatmap_value = (
                f"[{beatmap_name}]({self.bot.api.beatmap_url(beatmap_id)})"
                if beatmap_id and beatmap_name
                else str(beatmap_name or beatmap_id)
            )
            embed.add_field(name="Beatmap", value=beatmap_value, inline=False)

        score_id = metadata.get("score_id")
        if score_id:
            embed.add_field(name="Score", value=f"[Open score]({self.bot.api.score_url(score_id)})", inline=True)

        reasons = metadata.get("reasons")
        if isinstance(reasons, list) and reasons:
            embed.add_field(name="Why it tripped", value="\n".join(f"- {reason}" for reason in reasons[:6]), inline=False)

        if metadata.get("pp") is not None or metadata.get("accuracy") is not None:
            pp = metadata.get("pp")
            acc = metadata.get("accuracy")
            mods = metadata.get("mods") or "NM"
            rank = metadata.get("rank") or "?"
            embed.add_field(
                name="Play",
                value=f"{pp}pp - {acc}% - +{mods} - rank {rank}",
                inline=True,
            )

        related_users = metadata.get("related_users")
        if isinstance(related_users, list) and related_users:
            embed.add_field(name="Related accounts", value=", ".join(str(user) for user in related_users[:8]), inline=False)

        ip_address = metadata.get("ip_address")
        if ip_address:
            embed.add_field(name="IP", value=str(ip_address), inline=True)

        client_label = metadata.get("client_label")
        if client_label:
            embed.add_field(name="Client", value=str(client_label), inline=True)

        version_hash = metadata.get("version_hash") or metadata.get("last_client_hash")
        if version_hash:
            embed.add_field(name="Client hash", value=f"`{str(version_hash)[:32]}`", inline=True)

        return embed


async def setup(bot) -> None:
    await bot.add_cog(ModAlertsCog(bot))

