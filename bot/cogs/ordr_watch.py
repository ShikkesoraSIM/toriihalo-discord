from __future__ import annotations

import logging

import discord
from discord.ext import commands, tasks

from bot.torii_api import ToriiApiError, ToriiApiUnauthorized


logger = logging.getLogger(__name__)

# colores por estado del render
_COLOR_QUEUED = discord.Color.from_rgb(255, 211, 110)   # ambar
_COLOR_RENDERING = discord.Color.from_rgb(88, 166, 255)  # azul
_COLOR_DONE = discord.Color.from_rgb(87, 242, 135)       # verde
_COLOR_FAILED = discord.Color.from_rgb(237, 66, 69)      # rojo


class OrdrWatchCog(commands.Cog):
    """Postea + edita en vivo el status de los renders de o!rdr compartidos.

    Flujo estilo yuna: apenas un render compartido entra en la cola, posteamos un
    mensaje ("X queued a replay...") y lo VAMOS EDITANDO con el progreso (%, host)
    hasta que termina, momento en el que editamos al video final. El server
    guarda el discord_message_id asi el mensaje sobrevive a reinicios del bot; en
    memoria solo llevamos el ultimo estado dibujado para no re-editar de mas.
    """

    def __init__(self, bot) -> None:
        self.bot = bot
        # record_id -> ultimo (status, progress, renderer) que dibujamos, para no
        # spamear ediciones cuando o!rdr no cambio nada.
        self._last_drawn: dict[int, tuple] = {}
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

    @tasks.loop(seconds=8.0)
    async def poll_renders(self) -> None:
        poll_seconds = max(5.0, float(self.bot.settings.ordr_watch_poll_seconds))
        if abs(self.poll_renders.seconds - poll_seconds) > 0.001:
            self.poll_renders.change_interval(seconds=poll_seconds)

        channel = await self._resolve_channel()
        if channel is None or not self.bot.settings.mod_alert_token:
            return

        try:
            renders = await self.bot.api.get_active_ordr_renders(limit=15)
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
                await self._process(channel, render)
            except Exception as exc:
                logger.exception("Failed to process ordr render %s: %s", render.get("id"), exc)

    async def _process(self, channel: discord.TextChannel, render: dict) -> None:
        record_id = int(render["id"])
        status = str(render.get("status") or "queued")
        progress = str(render.get("progress") or "")
        renderer = render.get("renderer")
        message_id = render.get("discord_message_id")
        terminal = status in ("done", "failed")

        # sin cambios y no es terminal -> nada que hacer (evita editar de mas).
        signature = (status, progress, renderer)
        if message_id and not terminal and self._last_drawn.get(record_id) == signature:
            return

        content, embed = self._render_message(render)

        if not message_id:
            # primer avistaje: postear el mensaje y guardar su id en el server.
            message = await channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions.none())
            try:
                await self.bot.api.set_ordr_render_message(record_id, message.id)
            except Exception as exc:
                logger.warning("Could not store discord message id for render %s: %s", record_id, exc)
            if self.bot.settings.ordr_watch_create_threads:
                await self._try_thread(message, render)
            self._last_drawn[record_id] = signature
            if terminal:
                await self._finalize(record_id)
            return

        # ya existe el mensaje: editarlo con el estado nuevo.
        try:
            partial = channel.get_partial_message(int(message_id))
            await partial.edit(content=content, embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.NotFound:
            # borraron el mensaje: reposteamos y re-guardamos el id.
            message = await channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions.none())
            try:
                await self.bot.api.set_ordr_render_message(record_id, message.id)
            except Exception:
                pass
        except discord.DiscordException as exc:
            logger.warning("Could not edit render message %s: %s", record_id, exc)
            return

        self._last_drawn[record_id] = signature
        if terminal:
            await self._finalize(record_id)

    async def _finalize(self, record_id: int) -> None:
        """Marca dispatched (deja de aparecer en /active) + limpia el cache."""
        try:
            await self.bot.api.mark_ordr_render_dispatched(record_id)
        except Exception as exc:
            logger.warning("Could not mark render %s dispatched: %s", record_id, exc)
        self._last_drawn.pop(record_id, None)

    def _render_message(self, render: dict) -> tuple[str | None, discord.Embed]:
        username = str(render.get("username") or "someone")
        title = str(render.get("beatmap_title") or "").strip()
        status = str(render.get("status") or "queued")
        progress = str(render.get("progress") or "").strip()
        renderer = render.get("renderer")
        video_url = render.get("video_url")

        if status == "done" and video_url:
            embed = discord.Embed(color=_COLOR_DONE)
            embed.set_author(name=f"{username} rendered a replay")
            if title:
                embed.description = f"**{title}**"
            # el link como content hace que discord embeba el player de o!rdr.
            return video_url, embed

        if status == "failed":
            embed = discord.Embed(color=_COLOR_FAILED)
            embed.set_author(name=f"{username}'s render failed")
            embed.description = str(render.get("error_message") or "o!rdr couldn't render this replay.")
            return None, embed

        # en cola / rendereando
        rendering = status == "rendering"
        embed = discord.Embed(color=_COLOR_RENDERING if rendering else _COLOR_QUEUED)
        verb = "is rendering a replay" if rendering else "queued a replay"
        embed.set_author(name=f"{username} {verb}")
        if title:
            embed.description = f"**{title}**"

        status_line = progress or ("Rendering…" if rendering else "Waiting in o!rdr's queue…")
        if renderer and rendering:
            status_line = f"{status_line} · on {renderer}"
        embed.add_field(name="Status", value=status_line, inline=False)
        return None, embed

    async def _try_thread(self, message: discord.Message, render: dict) -> None:
        try:
            username = str(render.get("username") or "render")
            title = str(render.get("beatmap_title") or "").strip()
            name = f"\N{SPEECH BALLOON} {username}"
            if title:
                name = f"\N{SPEECH BALLOON} {username} - {title}"[:100]
            await message.create_thread(name=name, auto_archive_duration=1440)
        except discord.DiscordException as exc:
            logger.warning("Could not create thread for render %s: %s", render.get("id"), exc)

    @poll_renders.before_loop
    async def before_poll_renders(self) -> None:
        await self.bot.wait_until_ready()

    @commands.command(name="ordrwatch")
    @commands.is_owner()
    async def manual_poll(self, ctx: commands.Context) -> None:
        await self.poll_renders()
        await ctx.reply("ordr watch tick done", mention_author=False)


async def setup(bot) -> None:
    await bot.add_cog(OrdrWatchCog(bot))
