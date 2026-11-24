from __future__ import annotations

import asyncio
import math
import re
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


def _mods(value: object) -> list[tuple[str, dict]]:
    if isinstance(value, str):
        return [(name, {}) for name in re.findall(r"[A-Z]{2}", value.upper())]
    if not isinstance(value, list):
        return []
    return [(str(mod.get("acronym", "")).upper(), mod.get("settings") or {})
            if isinstance(mod, dict) else (str(mod).upper(), {}) for mod in value]


def adjusted_map_stats(beatmap: dict, mods: object, mode: str) -> dict:
    stats = {key: _number(beatmap.get(key)) for key in ("cs", "ar", "accuracy", "drain", "bpm", "total_length")}
    selected = dict(_mods(mods))
    rate = 1.0
    # NC/DT y DC/HT pueden venir juntos en scores legacy: no duplicar el rate.
    for names, default in ((("NC", "DT"), 1.5), (("DC", "HT"), 0.75)):
        for name in names:
            if name in selected:
                candidate = _number(selected[name].get("speed_change", default))
                rate *= candidate if candidate is not None and candidate > 0 else default
                break
    if "EZ" in selected:
        for key in ("cs", "ar", "accuracy", "drain"):
            if stats[key] is not None and not (mode == "mania" and key == "cs"):
                stats[key] *= 0.5
    if "HR" in selected:
        for key, multiplier in (("cs", 1.3), ("ar", 1.4), ("accuracy", 1.4), ("drain", 1.4)):
            if stats[key] is not None and not (mode == "mania" and key == "cs"):
                stats[key] = min(10.0, stats[key] * multiplier)
    da = selected.get("DA", {})
    for key, setting in (("cs", "circle_size"), ("ar", "approach_rate"), ("accuracy", "overall_difficulty"), ("drain", "drain_rate")):
        if (override := _number(da.get(setting))) is not None:
            stats[key] = override
    variable_rate = bool({"WU", "WD", "AS"} & selected.keys())
    if variable_rate:
        stats.update(bpm=None, total_length=None, ar=None, accuracy=None)
    else:
        if stats["bpm"] is not None:
            stats["bpm"] *= rate
        if stats["total_length"] is not None:
            stats["total_length"] /= rate
        if mode.startswith(("osu", "fruits")) and stats["ar"] is not None and rate != 1:
            ar = stats["ar"]
            preempt = (1800 - 120 * ar if ar <= 5 else 1200 - 150 * (ar - 5)) / rate
            stats["ar"] = (1800 - preempt) / 120 if preempt >= 1200 else 5 + (1200 - preempt) / 150
        if mode.startswith("osu") and stats["accuracy"] is not None and rate != 1:
            stats["accuracy"] = (80 - (80 - 6 * stats["accuracy"]) / rate) / 6
        elif mode.startswith("taiko") and stats["accuracy"] is not None and rate != 1:
            stats["accuracy"] = (50 - (50 - 3 * stats["accuracy"]) / rate) / 3
    stats["rate"] = rate
    stats["variable_rate"] = variable_rate
    return stats


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

    def __init__(self, owner_id: int, user: dict, scores: list[dict], mode: str, web_base: str, index: int = 0, emojis: dict[str, str] | None = None):
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
        self.compact = False
        self.emojis = emojis or {}
        self.message: discord.WebhookMessage | discord.Message | None = None
        self._navigation_lock = asyncio.Lock()
        self.score_link = discord.ui.Button(label="Open score", url=self.web_base, row=0)
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
        grade = self.emojis.get(f"torii_grade_{rank.lower()}", _text(rank, '?', 5))
        embed = discord.Embed(color=0xEF779D if rank == "F" else 0x55C9C3)
        username = str(self.user.get("username") or "Unknown player").replace("\n", " ")[:80]
        author = {"name": f"{username} | {mode_display_name(self.mode)}"}
        if type(self.user.get("id")) is int:
            author["url"] = f"{self.web_base}/users/{self.user['id']}"
        if avatar := _image(self.user.get("avatar_url")):
            author["icon_url"] = avatar
        embed.set_author(**author)
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
                item_rank = str(item.get("rank") or "?").upper()
                item_grade = self.emojis.get(f"torii_grade_{item_rank.lower()}", _text(item_rank, '?', 5))
                embed.add_field(name=f"#{i + 1}", value=f"{item_grade} [{title} [{difficulty}]]({link})\n{summary}", inline=False)
            return embed

        embed.title = f"{beatmapset.get('artist') or 'Unknown artist'} - {beatmapset.get('title') or 'Unknown map'} [{beatmap.get('version') or 'Unknown difficulty'}]"[:256]
        if current_id := score_id(score):
            embed.url = f"{self.web_base}/scores/{current_id}"
        acc = _number(score.get("accuracy"))
        adjusted = adjusted_map_stats(beatmap, score.get("mods"), self.mode)
        attributes = []
        for key, label in (("cs", "CS"), ("ar", "AR"), ("accuracy", "OD"), ("drain", "HP")):
            if self.mode.startswith("taiko") and key in ("cs", "ar"):
                continue
            if self.mode == "mania" and key == "ar":
                continue
            if self.mode.startswith("fruits") and key == "accuracy":
                continue
            if self.mode == "mania" and key == "accuracy":
                label = "OD (set)"
            if self.mode == "mania" and key == "cs":
                label = "Keys"
            attributes.append(f"{label} {_value(adjusted[key], 1)}")
        duration = adjusted["total_length"]
        length = f"{int(duration) // 60}:{int(duration) % 60:02}" if duration is not None and duration >= 0 else "--:--"
        attributes.append(f"BPM {_value(adjusted['bpm'], 1)}")
        attributes.append(length)
        played_text = ""
        try:
            played = datetime.fromisoformat(str(score.get("ended_at") or score.get("created_at")).replace("Z", "+00:00"))
            if played.tzinfo is not None:
                played_text = " | " + discord.utils.format_dt(played, "R")
        except ValueError:
            pass
        embed.description = (
            f"{grade} **+{_text(format_mods(score.get('mods')), 'NM', 200)}**  "
            f"{_value(score.get('total_score', score.get('score')))}  **{format_accuracy(acc) if acc is not None else '--'}**{played_text}\n"
            f"**{_value(score.get('pp'), 2, 'pp')}** | **{_value(score.get('max_combo'))}x** / {_value(beatmap.get('max_combo'))}x\n"
            f"{_judgements(score, self.mode).replace('Miss:', self.emojis.get('torii_miss', 'Miss') + ':')}\n"
            f"`{' | '.join(attributes)}` | {_value(beatmap.get('difficulty_rating'), 2)}* NM"
        )
        covers = beatmapset.get("covers") or {}
        keys = ("list", "card", "cover") if self.compact else ("cover", "card", "list")
        if cover := next((url for key in keys if (url := _image(covers.get(key)))), None):
            if self.compact:
                embed.set_thumbnail(url=cover)
            else:
                embed.set_image(url=cover)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Run /rs to browse your own results.", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        async with self._navigation_lock:
            self.compact = True
            for child in list(self.children):
                if not isinstance(child, discord.ui.Button) or child.style != discord.ButtonStyle.link:
                    child.disabled = True
                    self.remove_item(child)
            if self.message:
                try:
                    await self.message.edit(embed=self.embed(), view=self)
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

