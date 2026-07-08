"""Canned responses / tags para staff.

`t!send <key>` postea un mensaje pre-escrito. Reply-aware: si respondes al
mensaje de alguien, el canned le contesta a esa persona (le queda claro a quien
va). Borra el comando del staff para no ensuciar el canal. Solo staff (permiso
"manage messages" / "manage guild" / admin, u owner).

Los textos son editables EN VIVO (no hace falta redeploy) con:
    t!canned list                  ver todos los keys
    t!canned set <key> <texto>     crear/editar
    t!canned del <key>             borrar (custom; un default se sobreescribe)
    t!canned show <key>            ver el texto completo

Los custom se guardan en la KV del bot (sqlite) y se overlayean sobre DEFAULTS.
El texto que ve la comunidad va en INGLES.
"""
from __future__ import annotations

import json
import logging
import time

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)

KV_KEY = "canned:responses"

# defaults (editables en vivo con `t!canned set`). community-facing => ingles.
DEFAULTS: dict[str, str] = {
    "bugreport": "please post bug reports in the bug reports channel, not here. it keeps them from getting lost. thanks!",
    "namechange": "staff review name changes when they can. please be patient, no need to ping.",
    "patience": "staff are aware and working on it. please be patient. 🙏",
    "ping": "please don't ping staff members. we'll get to it.",
    "banned": "looks like you're banned. please open a support ticket and staff will look into it.",
    "ticket": "please open a support ticket for this so it doesn't get lost in chat.",
    "downtime": "we're aware of the downtime and already working on it. thanks for your patience.",
    "updates": "future updates get announced when they're ready. there's no eta, please be patient.",
    "wrongchannel": "this isn't the right channel for that. please use the appropriate one, thanks!",
}


class CannedCog(commands.Cog):
    """Respuestas pre-escritas para el staff (`t!send <key>`)."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self._ping_cooldown: dict[int, float] = {}  # {author_id: last_warn_ts}

    # ---- helpers -----------------------------------------------------

    def _is_staff(self, author) -> bool:
        if author.id in set(self.bot.settings.discord_owner_ids):
            return True
        perms = getattr(author, "guild_permissions", None)
        return bool(perms and (perms.manage_messages or perms.manage_guild or perms.administrator))

    async def _load_custom(self) -> dict[str, str]:
        try:
            raw = await self.bot.db.kv_get(KV_KEY)
            if raw:
                d = json.loads(raw)
                if isinstance(d, dict):
                    return {str(k).lower(): str(v) for k, v in d.items()}
        except Exception as exc:
            logger.warning("canned: failed to read custom responses: %s", exc)
        return {}

    async def _all(self) -> dict[str, str]:
        merged = dict(DEFAULTS)
        merged.update(await self._load_custom())
        return merged

    async def _save_custom(self, custom: dict[str, str]) -> None:
        await self.bot.db.kv_set(KV_KEY, json.dumps(custom))

    # ---- guard: avisa si un no-staff pinguea a staff protegido -------

    @commands.Cog.listener("on_message")
    async def _staff_ping_guard(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        watched = set(getattr(self.bot.settings, "staff_ping_guard_user_ids", None) or [])
        if not watched:
            return
        content = message.content or ""
        # solo @pings DIRECTOS en el texto (no replies, no role-pings)
        if not any(f"<@{uid}>" in content or f"<@!{uid}>" in content for uid in watched):
            return
        # no avisar si el que pinguea es uno de los protegidos, o es staff
        if message.author.id in watched or self._is_staff(message.author):
            return
        # cooldown por usuario para no spamear
        now = time.time()
        if now - self._ping_cooldown.get(message.author.id, 0.0) < 300:
            return
        self._ping_cooldown[message.author.id] = now
        responses = await self._all()
        text = responses.get("ping") or "please don't ping staff members."
        try:
            await message.reply(
                text,
                allowed_mentions=discord.AllowedMentions(
                    replied_user=True, everyone=False, users=False, roles=False
                ),
            )
        except discord.DiscordException as exc:
            logger.warning("canned: staff ping guard reply failed: %s", exc)

    # ---- t!send <key> ------------------------------------------------

    @commands.command(name="send")
    async def send_canned(self, ctx: commands.Context, key: str | None = None) -> None:
        if not self._is_staff(ctx.author):
            return
        responses = await self._all()
        if not key or key.lower() not in responses:
            keys = ", ".join(f"`{k}`" for k in sorted(responses))
            await ctx.reply(
                f"unknown key. available: {keys}\n(`t!canned show <key>` to preview)",
                mention_author=False, delete_after=30,
            )
            return

        text = responses[key.lower()]
        ref = ctx.message.reference
        try:
            if ref and ref.message_id:
                target = ref.resolved or await ctx.channel.fetch_message(ref.message_id)
                await target.reply(text, mention_author=True)
            else:
                await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
        except discord.DiscordException as exc:
            logger.warning("canned: failed to post '%s': %s", key, exc)
            return

        # limpia el comando del staff (si el bot puede borrar en ese canal)
        try:
            await ctx.message.delete()
        except discord.DiscordException:
            pass

    # ---- t!canned (list/set/del/show) --------------------------------

    @commands.group(name="canned", invoke_without_command=True)
    async def canned(self, ctx: commands.Context) -> None:
        if not self._is_staff(ctx.author):
            return
        await ctx.reply(
            "usage: `t!canned list` · `t!canned set <key> <text>` · "
            "`t!canned del <key>` · `t!canned show <key>` · and `t!send <key>` to post.",
            mention_author=False,
        )

    @canned.command(name="list")
    async def canned_list(self, ctx: commands.Context) -> None:
        if not self._is_staff(ctx.author):
            return
        responses = await self._all()
        custom = await self._load_custom()
        lines = []
        for k in sorted(responses):
            tag = " *(custom)*" if k in custom else ""
            body = responses[k]
            preview = body[:70] + ("…" if len(body) > 70 else "")
            lines.append(f"`{k}`{tag} — {preview}")
        embed = discord.Embed(
            title="Canned responses",
            description="\n".join(lines) or "none",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="t!send <key> to post · t!canned set <key> <text> to edit")
        await ctx.reply(embed=embed, mention_author=False)

    @canned.command(name="set")
    async def canned_set(self, ctx: commands.Context, key: str, *, text: str) -> None:
        if not self._is_staff(ctx.author):
            return
        k = key.lower().strip()
        if not k:
            await ctx.reply("i need a key.", mention_author=False)
            return
        custom = await self._load_custom()
        custom[k] = text.strip()
        await self._save_custom(custom)
        await ctx.reply(f"saved `{k}`. try it with `t!send {k}`.", mention_author=False)

    @canned.command(name="del")
    async def canned_del(self, ctx: commands.Context, key: str) -> None:
        if not self._is_staff(ctx.author):
            return
        k = key.lower().strip()
        custom = await self._load_custom()
        if k in custom:
            del custom[k]
            await self._save_custom(custom)
            note = " (falls back to the default)" if k in DEFAULTS else ""
            await ctx.reply(f"deleted `{k}`.{note}", mention_author=False)
        else:
            await ctx.reply(
                f"`{k}` isn't a custom response. defaults can't be deleted, but you can override it with `t!canned set {k} ...`.",
                mention_author=False,
            )

    @canned.command(name="show")
    async def canned_show(self, ctx: commands.Context, key: str) -> None:
        if not self._is_staff(ctx.author):
            return
        responses = await self._all()
        k = key.lower().strip()
        if k in responses:
            await ctx.reply(f"`{k}`:\n>>> {responses[k]}", mention_author=False)
        else:
            await ctx.reply(f"`{k}` doesn't exist. use `t!canned list` to see the keys.", mention_author=False)


async def setup(bot) -> None:
    await bot.add_cog(CannedCog(bot))
