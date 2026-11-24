from __future__ import annotations

import asyncio
import math
from datetime import datetime
from urllib.parse import urlsplit

import discord

from bot.utils.formatting import format_accuracy, format_mods, mode_display_name


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _value(value: object, decimals: int = 0, suffix: str = "") -> str:
    number = _number(value)
    return f"{number:,.{decimals}f}{suffix}" if number is not None else "--"


def _text(value: object, fallback: str, limit: int = 100) -> str:
    text = str(value or fallback).replace("\n", " ")
    return discord.utils.escape_markdown(text[:limit])


def _image(value: object) -> str | None:
    try:
        if isinstance(value, str) and len(value) <= 2048 and urlsplit(value).scheme == "https" and urlsplit(value).hostname:
            return value
    except ValueError:
        pass
    return None


def score_id(score: dict) -> int | None:
    value = score.get("id")
    return value if type(value) is int and value > 0 else None


def _judgements(score: dict, mode: str) -> str:
    stats = score.get("statistics") or {}
    groups = {
        "mania": [
            ("MAX", "perfect", "count_geki"), ("300", "great", "count_300"),
            ("200", "good", "count_katu"), ("100", "ok", "count_100"),
            ("50", "meh", "count_50"), ("Miss", "miss", "count_miss"),
        ],
        "taiko": [
            ("300", "great", "count_300"), ("100", "ok", "count_100"), ("Miss", "miss", "count_miss"),
        ],
        "fruits": [
            ("Fruit", "great", "count_300"), ("Drop", "large_tick_hit", "count_100"),
            ("Tiny", "small_tick_hit", "count_50"), ("Tiny miss", "small_tick_miss", "count_katu"),
            ("Miss", "miss", "count_miss"),
        ],
    }
    base = next((name for name in groups if mode.startswith(name)), "osu")
    columns = groups.get(base, [("300", "great", "count_300"), ("100", "ok", "count_100"), ("50", "meh", "count_50"), ("Miss", "miss", "count_miss")])
    return "  /  ".join(f"{label}: **{_value(stats.get(key, stats.get(legacy)))}**" for label, key, legacy in columns)


class RecentScoresView(discord.ui.View):
    """Las paginas usan el mismo snapshot; los botones no consultan la API."""

    def __init__(self, owner_id: int, user: dict, scores: list[dict], mode: str, web_base: str, index: int = 0):
        super().__init__(timeout=180)
        if not scores or not 0 <= index < len(scores):
            raise ValueError("Choose an available recent play.")
        self.owner_id = owner_id
        self.user = user
        self.scores = scores
        self.mode = mode
        self.web_base = web_base.rstrip("/")
        self.index = index
        self.list_mode = False
        self.message: discord.WebhookMessage | discord.Message | None = None
        self._navigation_lock = asyncio.Lock()
        self.score_link = discord.ui.Button(label="Open score", style=discord.ButtonStyle.link, row=1)
        self.add_item(self.score_link)
        self._sync_controls()

    @property
    def list_start(self) -> int:
        return self.index // 5 * 5

    def _sync_controls(self) -> None:
        start = self.list_start if self.list_mode else self.index
        self.previous.disabled = start == 0
        self.next.disabled = start + (5 if self.list_mode else 1) >= len(self.scores)
        self.layout.label = "Details" if self.list_mode else "List"
        self.position.label = f"{start + 1}-{min(start + 5, len(self.scores))} / {len(self.scores)}" if self.list_mode else f"{self.index + 1} / {len(self.scores)}"
        current_id = score_id(self.scores[self.index])
        self.score_link.url = f"{self.web_base}/scores/{current_id}" if current_id else self.web_base
        self.score_link.disabled = current_id is None or self.list_mode

    def embed(self) -> discord.Embed:
        score = self.scores[self.index]
        beatmap = score.get("beatmap") or {}
        beatmapset = beatmap.get("beatmapset") or score.get("beatmapset") or {}
        rank = str(score.get("rank") or "?").upper()
        embed = discord.Embed(color=0xEF779D if rank == "F" else 0x55C9C3)
        username = str(self.user.get("username") or "Unknown player").replace("\n", " ")[:80]
        author = {"name": f"{username} | {mode_display_name(self.mode)}"}
        if type(self.user.get("id")) is int:
            author["url"] = f"{self.web_base}/users/{self.user['id']}"
        if avatar := _image(self.user.get("avatar_url")):
            author["icon_url"] = avatar
        embed.set_author(**author)
        embed.set_footer(text="ToriiHalo | PP from Torii | Recent plays snapshot")
        if self.list_mode:
            embed.title = "Recent plays"
            for i in range(self.list_start, min(self.list_start + 5, len(self.scores))):
                item = self.scores[i]
                bm = item.get("beatmap") or {}
                bs = bm.get("beatmapset") or item.get("beatmapset") or {}
                title = _text(bs.get("title"), "Unknown map", 70)
                difficulty = _text(bm.get("version"), "Unknown difficulty", 50)
                link = f"{self.web_base}/scores/{score_id(item)}" if score_id(item) else self.web_base
                acc = _number(item.get("accuracy"))
                summary = f"**{_value(item.get('pp'), 2, 'pp')}** | {format_accuracy(acc) if acc is not None else '--'} | {_text(format_mods(item.get('mods')), 'NM', 140)}"
                embed.add_field(name=f"{i + 1}. {_text(item.get('rank'), '?', 5)}", value=f"[{title} [{difficulty}]]({link})\n{summary}", inline=False)
            return embed

        embed.title = f"{beatmapset.get('artist') or 'Unknown artist'} - {beatmapset.get('title') or 'Unknown map'} [{beatmap.get('version') or 'Unknown difficulty'}]"[:256]
        if current_id := score_id(score):
            embed.url = f"{self.web_base}/scores/{current_id}"
        embed.description = f"**{_text(rank, '?', 5)}**  +{_text(format_mods(score.get('mods')), 'NM', 200)}\n{_value(beatmap.get('difficulty_rating'), 2, '*')} NM"
        acc = _number(score.get("accuracy"))
        embed.add_field(name="Performance", value=f"**{_value(score.get('pp'), 2, 'pp')}**")
        embed.add_field(name="Accuracy", value=format_accuracy(acc) if acc is not None else "--")
        embed.add_field(name="Combo", value=f"{_value(score.get('max_combo'))}x / {_value(beatmap.get('max_combo'))}x")
        embed.add_field(name="Score", value=_value(score.get("total_score", score.get("score"))))
        embed.add_field(name="Judgements", value=_judgements(score, self.mode), inline=False)
        embed.add_field(name="Map (NM)", value=f"BPM {_value(beatmap.get('bpm'))} | CS {_value(beatmap.get('cs'), 1)} | AR {_value(beatmap.get('ar'), 1)} | OD {_value(beatmap.get('accuracy'), 1)} | HP {_value(beatmap.get('drain'), 1)}", inline=False)
        try:
            played = datetime.fromisoformat(str(score.get("ended_at") or score.get("created_at")).replace("Z", "+00:00"))
            if played.tzinfo is not None:
                embed.add_field(name="Played", value=discord.utils.format_dt(played, "R"))
        except ValueError:
            pass
        covers = beatmapset.get("covers") or {}
        if cover := next((url for key in ("card", "cover", "list") if (url := _image(covers.get(key)))), None):
            embed.set_image(url=cover)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Run /rs to browse your own results.", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        async with self._navigation_lock:
            for child in self.children:
                if not isinstance(child, discord.ui.Button) or child.style != discord.ButtonStyle.link:
                    child.disabled = True
            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.HTTPException:
                    pass

    async def _navigate(self, interaction: discord.Interaction, action: str) -> None:
        await interaction.response.defer()
        async with self._navigation_lock:
            if self.is_finished():
                return
            if action == "layout":
                self.list_mode = not self.list_mode
            elif action == "previous":
                self.index = max(0, self.list_start - 5) if self.list_mode else max(0, self.index - 1)
            elif action == "next":
                target = self.list_start + 5 if self.list_mode else self.index + 1
                if target < len(self.scores):
                    self.index = target
            self._sync_controls()
            await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(emoji="\N{BLACK LEFT-POINTING TRIANGLE}", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._navigate(interaction, "previous")

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.secondary, disabled=True)
    async def position(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        pass

    @discord.ui.button(emoji="\N{BLACK RIGHT-POINTING TRIANGLE}", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._navigate(interaction, "next")

    @discord.ui.button(label="List", style=discord.ButtonStyle.secondary)
    async def layout(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._navigate(interaction, "layout")

