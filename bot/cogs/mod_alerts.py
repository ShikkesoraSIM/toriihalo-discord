from __future__ import annotations

import io
import logging
from typing import Any

import discord
import httpx
from discord.ext import commands, tasks

from bot.torii_api import ToriiApiError, ToriiApiUnauthorized


logger = logging.getLogger(__name__)

SEVERITY_COLOURS = {
    "info": discord.Color.blue(),
    "warning": discord.Color.orange(),
    "critical": discord.Color.red(),
}

HIGH_PP_KIND = "high_pp_play"
BUTTON_PREFIX = "torii:highpp"


def build_high_pp_view(alert_id: int) -> discord.ui.View:
    """Los clicks se manejan en on_interaction, asi que los botones sobreviven un restart."""
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            label="Legit player",
            emoji="\N{WHITE HEAVY CHECK MARK}",
            style=discord.ButtonStyle.success,
            custom_id=f"{BUTTON_PREFIX}:whitelist:{alert_id}",
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Ban beatmapset",
            emoji="\N{NO ENTRY}",
            style=discord.ButtonStyle.danger,
            custom_id=f"{BUTTON_PREFIX}:ban:{alert_id}",
        )
    )
    view.add_item(
        discord.ui.Button(
            label="All plays",
            emoji="\N{CLIPBOARD}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"{BUTTON_PREFIX}:plays:{alert_id}",
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Dismiss",
            style=discord.ButtonStyle.secondary,
            custom_id=f"{BUTTON_PREFIX}:dismiss:{alert_id}",
        )
    )
    return view


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
                kind = str(alert.get("kind"))
                mention = (
                    "@here"
                    if self.bot.settings.mod_alert_mention_here and (severity == "critical" or kind == HIGH_PP_KIND)
                    else None
                )
                view = build_high_pp_view(int(alert["id"])) if kind == HIGH_PP_KIND else None
                # NSFW media uploads carry the offending image, reposted behind a
                # spoiler so the channel can eyeball it without it showing inline.
                spoiler_file = None
                if kind == "nsfw_media_upload":
                    metadata = alert.get("metadata") or {}
                    image_url = metadata.get("image_url") or metadata.get("url")
                    if image_url:
                        spoiler_file = await self._fetch_spoiler_image(str(image_url), metadata.get("media_type"))
                await channel.send(
                    content=mention,
                    embed=embed,
                    file=spoiler_file,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(everyone=True),
                )
                await self.bot.api.mark_mod_alert_dispatched(int(alert["id"]))
            except Exception as exc:
                logger.exception("Failed to post moderation alert %s: %s", alert.get("id"), exc)
                break

    @poll_mod_alerts.before_loop
    async def before_poll_mod_alerts(self) -> None:
        await self.bot.wait_until_ready()

    def _can_action(self, user: discord.abc.User) -> bool:
        if user.id in set(self.bot.settings.discord_owner_ids):
            return True
        return isinstance(user, discord.Member) and user.guild_permissions.administrator

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        custom_id = (interaction.data or {}).get("custom_id", "") if interaction.data else ""
        if not str(custom_id).startswith(f"{BUTTON_PREFIX}:"):
            return

        _, _, action, raw_id = str(custom_id).split(":", 3)
        alert_id = int(raw_id)

        if not self._can_action(interaction.user):
            await interaction.response.send_message("Administrators only.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self._run_action(interaction, action, alert_id)
        except Exception as exc:
            logger.exception("Mod alert action %s on %s failed: %s", action, alert_id, exc)
            await interaction.followup.send(f"That failed: `{exc}`", ephemeral=True)

    async def _run_action(self, interaction: discord.Interaction, action: str, alert_id: int) -> None:
        if action == "plays":
            user_id = self._alert_user_id(interaction)
            if user_id is None:
                await interaction.followup.send("Could not tell which player this alert is about.", ephemeral=True)
                return
            data = await self.bot.api.get_user_high_pp_plays(user_id, limit=25)
            plays = data.get("plays") or []
            if not plays:
                await interaction.followup.send("No plays above the threshold.", ephemeral=True)
                return
            lines = [
                f"`{play['pp']:>7.1f}pp` [{play['beatmap_name']}]({self.bot.api.score_url(play['score_id'])}) "
                f"- {play['accuracy']}% +{play['mods'] or 'NM'}"
                for play in plays
            ]
            embed = discord.Embed(
                title=f"{data.get('username') or user_id} - plays above {data.get('threshold')}pp",
                description="\n".join(lines)[:4000],
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if action == "whitelist":
            await self.bot.api.whitelist_high_pp_user(alert_id, interaction.user.id)
            resolution = f"Marked legit by {interaction.user.mention}, no more alerts for this player."
        elif action == "ban":
            result = await self.bot.api.ban_alert_beatmapset(
                alert_id, reason=f"banned by {interaction.user} from a high pp alert"
            )
            banned = result.get("banned", 0)
            resolution = (
                f"Beatmapset `{result.get('beatmapset_id')}` banned by {interaction.user.mention} "
                f"({banned} difficulties). Everyone with scores on it is being recalculated."
            )
        elif action == "dismiss":
            await self.bot.api.resolve_mod_alert(alert_id)
            resolution = f"Dismissed by {interaction.user.mention}."
        else:
            return

        await self._close_alert_message(interaction, resolution)
        await interaction.followup.send(resolution, ephemeral=True)

    def _alert_user_id(self, interaction: discord.Interaction) -> int | None:
        message = interaction.message
        if message is None or not message.embeds:
            return None
        for field in message.embeds[0].fields:
            if field.name == "User" and field.value and "#" in field.value:
                digits = field.value.split("#", 1)[1].split("]", 1)[0].strip()
                if digits.isdigit():
                    return int(digits)
        return None

    async def _close_alert_message(self, interaction: discord.Interaction, resolution: str) -> None:
        message = interaction.message
        if message is None:
            return
        embed = message.embeds[0] if message.embeds else discord.Embed()
        embed.add_field(name="Resolved", value=resolution, inline=False)
        embed.color = discord.Color.dark_grey()
        try:
            await message.edit(embed=embed, view=None)
        except discord.DiscordException as exc:
            logger.warning("Could not close alert message %s: %s", message.id, exc)

    async def _fetch_spoiler_image(self, url: str, media_type: str | None = None) -> discord.File | None:
        """Download an uploaded image so it can be reposted as a spoiler attachment.

        Discord only blurs file attachments flagged as spoilers (embeds cannot be
        spoilered), so we pull the bytes ourselves and hand them back as a
        spoiler-flagged discord.File. Returns None on any failure; the caller
        still posts the text embed without the image.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.content
        except Exception as exc:
            logger.warning("Failed to download NSFW media %s: %s", url, exc)
            return None
        if not data:
            return None
        ctype = resp.headers.get("content-type", "").lower()
        ext = "png"
        if "gif" in ctype:
            ext = "gif"
        elif "webp" in ctype:
            ext = "webp"
        elif "jpeg" in ctype or "jpg" in ctype:
            ext = "jpg"
        label = media_type if media_type in ("avatar", "cover") else "media"
        return discord.File(io.BytesIO(data), filename=f"nsfw_{label}.{ext}", spoiler=True)

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

