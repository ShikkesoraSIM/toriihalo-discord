"""Watcher de la agenda de daily challenges.

Una vez por dia (00:05 UTC, justo despues de que rota el daily challenge)
chequea cuantos dias de daily challenge hay agendados por delante. Si el
buffer baja del minimo configurado (default 2 dias), pinguea el canal de
mods con un @here para que alguien agende mas antes de que los jugadores
lleguen a un dia sin challenge.

La agenda vive en el server, en la tabla `daily_challenge` (una fila por
fecha). La leemos por el endpoint privado
`/api/private/daily-challenge/schedule`, con el mismo MOD_ALERT_TOKEN que
usa el poller de mod-alerts.

Cadencia: un solo tick diario via `tasks.loop(time=...)`. No hace falta
dedup mas alla de eso: si el buffer sigue bajo, avisa una vez por dia
hasta que se arregle, que es justamente lo que queremos.
"""

from __future__ import annotations

import datetime as dt
import logging

import discord
from discord.ext import commands, tasks


logger = logging.getLogger(__name__)

# chequeo diario a las 00:05 UTC (recien rotado el daily challenge).
CHECK_TIME = dt.time(hour=0, minute=5, tzinfo=dt.timezone.utc)


class DailyChallengeWatchCog(commands.Cog):
    """Avisa en el canal de mods cuando el buffer de daily challenges baja."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self._channel_warned = False
        self.daily_check.start()

    def cog_unload(self) -> None:
        self.daily_check.cancel()

    # ---- resolucion de canal (mismo patron que upstream_watch) -------

    async def _resolve_channel(self) -> discord.TextChannel | None:
        channel_id = (
            self.bot.settings.daily_challenge_watch_channel_id
            or self.bot.settings.mod_alert_channel_id
        )
        if not channel_id:
            return None

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.DiscordException as exc:
                if not self._channel_warned:
                    logger.warning(
                        "daily_challenge_watch: no pude traer el canal %s: %s",
                        channel_id, exc,
                    )
                    self._channel_warned = True
                return None

        if isinstance(channel, discord.TextChannel):
            self._channel_warned = False
            return channel
        if not self._channel_warned:
            logger.warning(
                "daily_challenge_watch: el canal %s no es de texto", channel_id
            )
            self._channel_warned = True
        return None

    # ---- loop diario -------------------------------------------------

    @tasks.loop(time=CHECK_TIME)
    async def daily_check(self) -> None:
        try:
            schedule = await self.bot.api.get_daily_challenge_schedule()
        except Exception as exc:
            logger.warning("daily_challenge_watch: fallo al leer la agenda: %s", exc)
            return

        buffer_days = int(schedule.get("buffer_days", 0))
        threshold = max(0, int(self.bot.settings.daily_challenge_watch_min_buffer_days))

        if buffer_days >= threshold:
            logger.info(
                "daily_challenge_watch: ok, %d dia(s) agendados por delante (umbral %d)",
                buffer_days, threshold,
            )
            return

        channel = await self._resolve_channel()
        if channel is None:
            logger.warning(
                "daily_challenge_watch: buffer bajo (%d) pero no hay canal configurado",
                buffer_days,
            )
            return

        embed = self._build_embed(schedule, threshold)
        mention = "@here" if self.bot.settings.daily_challenge_watch_mention_here else None
        try:
            await channel.send(
                content=mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(everyone=True),
            )
            logger.info(
                "daily_challenge_watch: avise, buffer=%d umbral=%d", buffer_days, threshold
            )
        except Exception as exc:
            logger.exception("daily_challenge_watch: fallo al postear el aviso: %s", exc)

    @daily_check.before_loop
    async def before_daily_check(self) -> None:
        await self.bot.wait_until_ready()

    # ---- embed -------------------------------------------------------

    def _build_embed(self, schedule: dict, threshold: int) -> discord.Embed:
        buffer_days = int(schedule.get("buffer_days", 0))
        today = schedule.get("today", "?")
        furthest = schedule.get("furthest_date") or "ninguno"
        upcoming = schedule.get("scheduled_dates") or []
        has_today = bool(schedule.get("has_today", False))

        if not has_today:
            title = "⚠️ No hay daily challenge para HOY"
        elif buffer_days <= 0:
            title = "⚠️ No hay daily challenge agendado para mañana"
        else:
            title = f"⚠️ Quedan solo {buffer_days} día(s) de daily challenge agendados"

        lines = [
            f"Hoy (`{today}`): {'agendado' if has_today else 'SIN daily challenge'}",
            f"Días agendados por delante (desde mañana): **{buffer_days}**",
            f"Última fecha agendada: `{furthest}`",
            "",
            f"Hace falta agendar más daily challenges: el buffer bajó de {threshold} días.",
        ]
        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        if upcoming:
            embed.add_field(
                name="Próximos agendados",
                value="\n".join(f"`{d}`" for d in upcoming[:10]),
                inline=False,
            )
        embed.set_footer(text="daily-challenge-watch · chequeo diario 00:05 UTC")
        return embed

    # ---- trigger manual (owner) para testear sin esperar a las 00:05 --

    @commands.command(name="dcwatch")
    @commands.is_owner()
    async def dcwatch_manual(self, ctx: commands.Context) -> None:
        try:
            schedule = await self.bot.api.get_daily_challenge_schedule()
        except Exception as exc:
            await ctx.reply(f"error leyendo la agenda: {exc}", mention_author=False)
            return
        threshold = max(0, int(self.bot.settings.daily_challenge_watch_min_buffer_days))
        embed = self._build_embed(schedule, threshold)
        # preview en el canal actual, SIN @here, para no pinguear a nadie al testear.
        await ctx.send(embed=embed)
        await ctx.reply(
            f"buffer={schedule.get('buffer_days')} umbral={threshold} "
            f"furthest={schedule.get('furthest_date')} has_today={schedule.get('has_today')}",
            mention_author=False,
        )


async def setup(bot) -> None:
    await bot.add_cog(DailyChallengeWatchCog(bot))
