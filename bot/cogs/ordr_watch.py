from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands, tasks

from bot.torii_api import ToriiApiError, ToriiApiUnauthorized


logger = logging.getLogger(__name__)

# base del sitio Torii para armar los links (perfil / mapa).
_TORII_WEB = "https://lazer.shikkesora.com"


def _masked(text: str, url: str | None) -> str:
    """Masked link de discord [text](<url>). Escapa []( ) del label para no romperlo.
    la url va entre <> para SUPRIMIR el embed del link (sino discord unfurlea la
    pagina de torii arriba del player del video). los mensajes de BOT si renderizan
    masked links en el content, a diferencia de los de usuario."""
    label = str(text).replace("[", "(").replace("]", ")")
    if not url:
        return label
    return f"[{label}](<{url}>)"


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
        # record_ids que ya finalizamos esta sesion: guard extra contra doble-post
        # del mensaje final si el dispatch al server tarda/falla y el render sigue
        # apareciendo en /active un ciclo mas.
        self._finalized: set[int] = set()
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

    @tasks.loop(seconds=4.0)
    async def poll_renders(self) -> None:
        poll_seconds = max(3.0, float(self.bot.settings.ordr_watch_poll_seconds))
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
        video_url = render.get("video_url")

        # ya lo cerramos esta sesion: no re-postear el final aunque siga en /active.
        if record_id in self._finalized:
            return

        # TERMINAL: video listo. borramos el mensaje de progreso (con su embed) y
        # posteamos uno NUEVO con SOLO el link, asi discord despliega el player de
        # o!rdr (con un embed propio del bot, discord NO auto-embebe el link).
        if status == "done" and video_url:
            await self._post_final(channel, render, message_id)
            await self._finalize(record_id)
            return

        if status == "failed":
            await self._post_failed(channel, render, message_id)
            await self._finalize(record_id)
            return

        # EN CURSO (queued/rendering): postear/editar el embed de status en vivo.
        signature = (status, progress, renderer)
        if message_id and self._last_drawn.get(record_id) == signature:
            return

        embed = self._progress_embed(render)

        if not message_id:
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            logger.info("Posted live-status message for render %s (status=%s)", record_id, status)
            try:
                await self.bot.api.set_ordr_render_message(record_id, message.id)
            except Exception as exc:
                logger.warning("Could not store discord message id for render %s: %s", record_id, exc)
        else:
            try:
                await channel.get_partial_message(int(message_id)).edit(
                    embed=embed, allowed_mentions=discord.AllowedMentions.none()
                )
            except discord.NotFound:
                message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                try:
                    await self.bot.api.set_ordr_render_message(record_id, message.id)
                except Exception:
                    pass
            except discord.DiscordException as exc:
                logger.warning("Could not edit render message %s: %s", record_id, exc)
                return

        self._last_drawn[record_id] = signature

    async def _post_final(self, channel: discord.TextChannel, render: dict, old_message_id) -> None:
        """Al terminar: borra el mensaje de progreso y postea uno NUEVO con solo el
        link (player embebido) + abre el thread ahi. si no hubo mensaje de progreso
        (render muy rapido), va directo al mensaje del video."""
        video_url = str(render.get("video_url") or "").strip()
        if not video_url:
            return

        # borrar el mensaje de progreso: su lugar lo toma el mensaje del video. (un
        # embed propio del bot bloquea el auto-embed del link, por eso va aparte.)
        if old_message_id:
            try:
                await channel.get_partial_message(int(old_message_id)).delete()
            except discord.DiscordException:
                pass

        # titulo con links: quien lo pidio, de QUIEN es la replay, y el mapa (todos
        # clickeables). el link del video va aparte (bare) para que embeba el player.
        content = f"{self._final_header(render)}\n{video_url}"
        message = await channel.send(content, allowed_mentions=discord.AllowedMentions.none())
        logger.info("Posted final video for render %s", render.get("id"))
        if self.bot.settings.ordr_watch_create_threads:
            await self._try_thread(message, render)

    def _final_header(self, render: dict) -> str:
        """'🎬 [submitter] rendered a replay played by [player] on [map]' con links."""
        submitter = str(render.get("username") or "someone")
        submitter_id = render.get("user_id")
        player = render.get("player_username")
        player_id = render.get("player_user_id")
        title = str(render.get("beatmap_title") or "").strip()
        setid = render.get("beatmapset_id")
        mapid = render.get("beatmap_online_id")
        mode = str(render.get("gamemode") or "osu")

        sub = _masked(submitter, f"{_TORII_WEB}/users/{submitter_id}" if submitter_id else None)

        if title and setid and mapid:
            map_part = _masked(title, f"{_TORII_WEB}/beatmapsets/{setid}#{mode}/{mapid}")
        elif title:
            map_part = _masked(title, None)
        else:
            map_part = "a replay"

        same = player and player_id and submitter_id and str(player_id) == str(submitter_id)
        if same:
            return f"\N{CLAPPER BOARD} {sub} rendered their replay on {map_part}"
        if player:
            plink = _masked(player, f"{_TORII_WEB}/users/{player_id}" if player_id else None)
            return f"\N{CLAPPER BOARD} {sub} rendered a replay played by {plink} on {map_part}"
        return f"\N{CLAPPER BOARD} {sub} rendered a replay on {map_part}"

    async def _post_failed(self, channel: discord.TextChannel, render: dict, message_id) -> None:
        username = str(render.get("username") or "someone")
        embed = discord.Embed(color=_COLOR_FAILED)
        embed.set_author(name=f"{username}'s render failed")
        embed.description = str(render.get("error_message") or "o!rdr couldn't render this replay.")
        if message_id:
            try:
                await channel.get_partial_message(int(message_id)).edit(
                    embed=embed, allowed_mentions=discord.AllowedMentions.none()
                )
                return
            except discord.DiscordException:
                pass
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def _finalize(self, record_id: int) -> None:
        """Marca dispatched (deja de aparecer en /active) + limpia el cache."""
        self._finalized.add(record_id)
        try:
            await self.bot.api.mark_ordr_render_dispatched(record_id)
        except Exception as exc:
            logger.warning("Could not mark render %s dispatched: %s", record_id, exc)
        self._last_drawn.pop(record_id, None)

    def _progress_embed(self, render: dict) -> discord.Embed:
        username = str(render.get("username") or "someone")
        title = str(render.get("beatmap_title") or "").strip()
        status = str(render.get("status") or "queued")
        progress = str(render.get("progress") or "").strip()
        renderer = render.get("renderer")

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
        return embed

    async def _try_thread(self, message: discord.Message, render: dict) -> None:
        # el thread para hablar del replay. abre en el mensaje del video. reintenta
        # una vez si el primer intento falla (rate limit / hiccup momentaneo de la API).
        player = str(render.get("player_username") or render.get("username") or "replay")
        title = str(render.get("beatmap_title") or "").strip()
        name = f"\N{SPEECH BALLOON} {player}"
        if title:
            name = f"\N{SPEECH BALLOON} {player} - {title}"[:100]

        for attempt in (1, 2):
            try:
                await message.create_thread(name=name, auto_archive_duration=1440)
                logger.info("Opened thread for render %s", render.get("id"))
                return
            except discord.DiscordException as exc:
                if attempt == 1:
                    logger.warning("Thread create failed for render %s (retrying): %s", render.get("id"), exc)
                    await asyncio.sleep(2)
                    continue
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
