from __future__ import annotations

import logging

import discord
from discord.ext import commands, tasks

from bot.torii_api import ToriiApiError, ToriiApiUnauthorized


logger = logging.getLogger(__name__)


class OrdrWatchCog(commands.Cog):
    """Postea los videos de replays renderizados via o!rdr.

    Mismo esquema que mod_alerts: el server (g0v0) guarda los renders
    terminados con share=True y este cog los polea, postea el link del video
    (discord embebe el player de o!rdr solo) y los marca dispatched para no
    repetir. La dedup vive en el server; el bot es stateless.

    Cada post abre un thread de comentarios para que la conversacion no
    ensucie el feed del canal (el slowmode del canal lo maneja discord).
    """

    def __init__(self, bot) -> None:
        self.bot = bot
        self.poll_renders.start()

    def cog_unload(self) -> None:
        self.poll_renders.cancel()

    async def _resolve_channel(self) -> discord.TextChannel | None:
        channel_id = self.bot.settings.ordr_watch_channel_id or self.bot.settings.mod_alert_channel_id
        if not channel_id:
            return None

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.DiscordException as exc:
                logger.warning("Failed to fetch ordr watch channel %s: %s", channel_id, exc)
                return None

        if isinstance(channel, discord.TextChannel):
            return channel
        logger.warning("Configured ordr watch channel %s is not a text channel.", channel_id)
        return None

    @tasks.loop(seconds=30.0)
    async def poll_renders(self) -> None:
        poll_seconds = max(10.0, float(self.bot.settings.ordr_watch_poll_seconds))
        if abs(self.poll_renders.seconds - poll_seconds) > 0.001:
            self.poll_renders.change_interval(seconds=poll_seconds)

        channel = await self._resolve_channel()
        if channel is None or not self.bot.settings.mod_alert_token:
            return

        try:
            renders = await self.bot.api.get_pending_ordr_renders(limit=5)
        except ToriiApiUnauthorized as exc:
            logger.warning("Ordr render polling unauthorized: %s", exc)
            return
        except ToriiApiError as exc:
            logger.warning("Ordr render polling failed: %s", exc)
            return
        except Exception as exc:
            logger.exception("Unexpected error while polling ordr renders: %s", exc)
            return

        for render in renders:
            try:
                await self._post_render(channel, render)
                await self.bot.api.mark_ordr_render_dispatched(int(render["id"]))
            except Exception as exc:
                logger.exception("Failed to post ordr render %s: %s", render.get("id"), exc)
                break

    async def _post_render(self, channel: discord.TextChannel, render: dict) -> None:
        username = str(render.get("username") or "someone")
        title = str(render.get("beatmap_title") or "").strip()
        video_url = str(render.get("video_url") or "").strip()
        if not video_url:
            return

        lines = [f"\N{CLAPPER BOARD} **{username}** rendered a replay"]
        if title:
            lines[0] += f" of **{title}**"
        lines.append(video_url)

        message = await channel.send(
            "\n".join(lines),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        if self.bot.settings.ordr_watch_create_threads:
            try:
                thread_name = f"\N{SPEECH BALLOON} {username}"
                if title:
                    # los nombres de thread topean en 100 chars
                    thread_name = f"\N{SPEECH BALLOON} {username} - {title}"[:100]
                await message.create_thread(name=thread_name, auto_archive_duration=1440)
            except discord.DiscordException as exc:
                # sin permiso de threads no es fatal: el video ya quedo posteado
                logger.warning("Could not create thread for render %s: %s", render.get("id"), exc)

    @poll_renders.before_loop
    async def before_poll_renders(self) -> None:
        await self.bot.wait_until_ready()

    @commands.command(name="ordrwatch")
    @commands.is_owner()
    async def manual_poll(self, ctx: commands.Context) -> None:
        """Trigger manual del poll (owner-only), para probar el flujo."""
        await self.poll_renders()
        await ctx.reply("ordr watch tick done", mention_author=False)


async def setup(bot) -> None:
    await bot.add_cog(OrdrWatchCog(bot))
