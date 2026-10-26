from __future__ import annotations

import asyncio
import datetime
import io
import json
import logging
import time

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)
CONFIG_KEY = "owner_ping:config"
DECAY_SECONDS = 30 * 24 * 3600
DEDUP_SECONDS = 60
HISTORY_LIMIT = 50


def active_count(state: dict, now: float) -> int:
    if now - state.get("last_at", 0) >= DECAY_SECONDS:
        return 0
    return int(state.get("count", 0))


def warning_text(count: int) -> str:
    action = "30 minute timeout" if count == 1 else "24 hour timeout" if count == 2 else "ban"
    return (
        f"warning {count} out of 3 for pinging the owner. action: {action}. "
        "second warning: 24 hour timeout, third warning: ban. "
        "please use a support ticket instead. warnings reset after 30 days without another owner ping."
    )


class OwnerPingGuardCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self._lock = asyncio.Lock()

    async def _config(self) -> dict:
        raw = await self.bot.db.kv_get(CONFIG_KEY)
        return json.loads(raw) if raw else {}

    def _key(self, guild_id: int, user_id: int) -> str:
        return f"owner_ping:member:{guild_id}:{user_id}"

    async def _state(self, guild_id: int, user_id: int) -> dict:
        raw = await self.bot.db.kv_get(self._key(guild_id, user_id))
        state = json.loads(raw) if raw else {"count": 0, "last_at": 0, "history": []}
        if not isinstance(state, dict) or not isinstance(state.get("history"), list):
            raise ValueError("invalid owner ping history")
        if not isinstance(state.get("count"), int) or state["count"] < 0:
            raise ValueError("invalid owner ping count")
        if not isinstance(state.get("last_at"), (int, float)):
            raise ValueError("invalid owner ping timestamp")
        return state

    async def _save(self, guild_id: int, user_id: int, state: dict) -> None:
        await self.bot.db.kv_set(self._key(guild_id, user_id), json.dumps(state))

    def _exempt(self, member, config: dict) -> bool:
        permissions = member.guild_permissions
        return (
            member.bot
            or member.id == member.guild.owner_id
            or permissions.administrator
            or permissions.manage_guild
            or permissions.manage_messages
            or any(role.id in config["exempt_role_ids"] for role in member.roles)
        )

    @commands.Cog.listener()
    async def on_automod_action(self, event: discord.AutoModAction) -> None:
        # AutoMod emite un evento por accion; contamos solo el timeout ya aplicado.
        if event.action.type != discord.AutoModRuleActionType.timeout:
            return
        try:
            config = await self._config()
            if not config.get("enabled") or (event.guild_id, event.rule_id) != (
                config["guild_id"], config["rule_id"]
            ):
                return
            if event.guild.owner_id != config["owner_id"]:
                return
            if event.action.duration != datetime.timedelta(minutes=30):
                logger.error("owner ping: unexpected native timeout; ignoring event")
                return
            member = event.member or await event.guild.fetch_member(event.user_id)
            if self._exempt(member, config):
                return
            async with self._lock:
                await self._record_and_apply(event, member, config)
        except Exception:
            logger.exception("owner ping: could not process AutoMod event")

    async def _record_and_apply(self, event, member, config: dict) -> None:
        now = time.time()
        state = await self._state(event.guild_id, event.user_id)
        if now - state["last_at"] < DEDUP_SECONDS:
            return
        if event.message_id and any(item.get("message_id") == event.message_id for item in state["history"]):
            return
        count = active_count(state, now) + 1
        incident = {
            "at": now, "count": count, "channel_id": event.channel_id,
            "message_id": event.message_id, "status": "pending", "dm": "pending",
        }
        state.update(count=count, last_at=now, history=(state["history"] + [incident])[-HISTORY_LIMIT:])
        # Si no se pudo guardar el aviso, no escalamos una sancion sin historial.
        await self._save(event.guild_id, event.user_id, state)
        try:
            await member.send(warning_text(count), allowed_mentions=discord.AllowedMentions.none())
            incident["dm"] = "sent"
        except discord.DiscordException:
            incident["dm"] = "unavailable"

        reason = f"owner ping: warning {count}/3; 30 day inactivity reset"
        try:
            if count == 2:
                await member.timeout(datetime.timedelta(hours=24), reason=reason)
                incident["status"] = "24 hour timeout"
            elif count >= 3:
                await event.guild.ban(member, reason=reason, delete_message_seconds=0)
                incident["status"] = "banned"
            else:
                incident["status"] = "30 minute timeout (AutoMod)"
        except discord.DiscordException as error:
            incident["status"] = f"escalation failed ({type(error).__name__}); native 30 minute timeout"
            logger.error("owner ping escalation failed: guild=%s user=%s warning=%s", event.guild_id, event.user_id, count)
        await self._save(event.guild_id, event.user_id, state)
        incident["owner_dm"] = await self._notify_owner(config, event, member, incident)
        await self._save(event.guild_id, event.user_id, state)
        await self._log(config, event.user_id, incident)

    async def _notify_owner(self, config: dict, event, member, incident: dict) -> str:
        content = event.content or "(Discord no incluyo el texto del mensaje)"
        preview = discord.utils.escape_mentions(discord.utils.escape_markdown(content))
        attachment = None
        if len(preview) > 3500:
            preview = preview[:3500] + "\n\nTexto completo en el adjunto."
            attachment = discord.File(io.BytesIO(content.encode("utf-8")), filename="mensaje-bloqueado.txt")
        channel = event.guild.get_channel_or_thread(event.channel_id) if event.channel_id else None
        channel_name = discord.utils.escape_markdown(channel.name) if channel else str(event.channel_id or "desconocido")
        status = {
            "30 minute timeout (AutoMod)": "Timeout de 30 minutos",
            "24 hour timeout": "Timeout de 24 horas",
            "banned": "Ban del Discord",
        }.get(incident["status"], "AutoMod aplico 30 minutos, pero fallo la escalada. Revisar el log de staff.")
        embed = discord.Embed(
            title="Alguien te taggeo. AutoMod bloqueo el mensaje.",
            description=preview,
            colour=discord.Colour.orange(),
            timestamp=datetime.datetime.fromtimestamp(incident["at"], tz=datetime.UTC),
        )
        author = discord.utils.escape_mentions(discord.utils.escape_markdown(member.display_name))
        embed.add_field(name="Quien", value=f"{author} ({member.id})", inline=False)
        channel_link = f"https://discord.com/channels/{event.guild_id}/{event.channel_id}"
        embed.add_field(name="Donde", value=f"[#{channel_name}]({channel_link})" if event.channel_id else channel_name)
        embed.add_field(name="Sancion aplicada", value=status)
        embed.set_footer(text=f"Aviso {incident['count']} de 3")
        try:
            owner = self.bot.get_user(config["owner_id"]) or await self.bot.fetch_user(config["owner_id"])
            await owner.send(
                embed=embed, file=attachment,
                allowed_mentions=discord.AllowedMentions.none(), silent=True,
            )
            return "sent"
        except discord.DiscordException:
            logger.warning("owner ping: owner DM unavailable; guild=%s", event.guild_id)
            return "unavailable"
        finally:
            if attachment is not None:
                attachment.close()

    async def _log(self, config: dict, user_id: int, incident: dict) -> None:
        logger.warning("owner ping: guild=%s user=%s incident=%s", config["guild_id"], user_id, json.dumps(incident))
        try:
            channel = self.bot.get_channel(config["log_channel_id"])
            if channel is None:
                channel = await self.bot.fetch_channel(config["log_channel_id"])
            embed = discord.Embed(title="owner ping warning", colour=discord.Colour.orange())
            embed.description = (
                f"user: {user_id}\nwarning: {incident['count']} out of 3\n"
                f"channel: {incident['channel_id']}\naction: {incident['status']}\n"
                f"DM: {incident['dm']}\nowner DM: {incident.get('owner_dm', 'not applicable')}\nwhen: <t:{int(incident['at'])}:f>"
            )
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.DiscordException:
            logger.exception("owner ping: staff log failed; incident is saved in the database")

    async def _staff_config(self, ctx: commands.Context, *, reset: bool = False) -> dict | None:
        config = await self._config()
        if ctx.guild is None or ctx.guild.id != config.get("guild_id"):
            return None
        permissions = ctx.author.guild_permissions
        can_manage = ctx.author.id == ctx.guild.owner_id or permissions.administrator or permissions.manage_guild
        can_read = can_manage or permissions.manage_messages or any(
            role.id in config["exempt_role_ids"] for role in ctx.author.roles
        )
        if not (can_manage if reset else can_read):
            return None
        if ctx.channel.id != config["log_channel_id"]:
            await ctx.reply("please use this command in the staff log channel.", mention_author=False)
            return None
        return config

    @commands.command(name="pingwarnings")
    async def ping_warnings(self, ctx: commands.Context, target: discord.User) -> None:
        if await self._staff_config(ctx) is None:
            return
        async with self._lock:
            state = await self._state(ctx.guild.id, target.id)
        lines = [f"user {target.id}: {active_count(state, time.time())} active owner ping warning(s)."]
        for item in state["history"][-10:]:
            lines.append(f"<t:{int(item['at'])}:f> - {item['status']} (warning {item['count']})")
        await ctx.reply("\n".join(lines), mention_author=False, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="pingwarningsclear")
    async def clear_warnings(self, ctx: commands.Context, target: discord.User) -> None:
        config = await self._staff_config(ctx, reset=True)
        if config is None:
            return
        async with self._lock:
            state = await self._state(ctx.guild.id, target.id)
            incident = {
                "at": time.time(), "count": state["count"], "channel_id": ctx.channel.id,
                "status": f"counter reset by {ctx.author.id}", "dm": "not applicable",
            }
            state.update(count=0, last_at=0, history=(state["history"] + [incident])[-HISTORY_LIMIT:])
            await self._save(ctx.guild.id, target.id, state)
        await self._log(config, target.id, incident)
        await ctx.reply("owner ping warnings cleared. history kept; this does not remove a ban or timeout.", mention_author=False)


async def setup(bot) -> None:
    await bot.add_cog(OwnerPingGuardCog(bot))
