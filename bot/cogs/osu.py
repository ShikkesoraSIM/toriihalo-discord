from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.torii_api import ToriiApiError, ToriiApiUnauthorized
from bot.utils import (
    clean_user_identifier,
    extract_beatmap_id,
    extract_score_id,
    format_accuracy,
    format_mods,
    format_number,
    format_pp,
    mode_display_name,
)


if TYPE_CHECKING:
    from bot.main import ToriiBot


MODE_CHOICES = [
    app_commands.Choice(name="osu!", value="osu"),
    app_commands.Choice(name="taiko", value="taiko"),
    app_commands.Choice(name="fruits", value="fruits"),
    app_commands.Choice(name="mania", value="mania"),
    app_commands.Choice(name="osu!rx", value="osurx"),
    app_commands.Choice(name="osu!ap", value="osuap"),
    app_commands.Choice(name="taiko rx", value="taikorx"),
    app_commands.Choice(name="fruits rx", value="fruitsrx"),
]

LEADERBOARD_TYPE_CHOICES = [
    app_commands.Choice(name="global", value="global"),
    app_commands.Choice(name="country", value="country"),
    app_commands.Choice(name="friends", value="friends"),
]

RANK_SORT_CHOICES = [
    app_commands.Choice(name="performance", value="performance"),
    app_commands.Choice(name="score", value="score"),
]


class OsuStatsCog(commands.Cog):
    def __init__(self, bot: ToriiBot) -> None:
        self.bot = bot

    async def _send_error(self, interaction: discord.Interaction, message: str) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def _resolve_user_identifier(self, interaction: discord.Interaction, user: str | None) -> str | int:
        if user:
            cleaned = clean_user_identifier(user)
            if cleaned:
                return cleaned
        link = await self.bot.db.get_linked_account(interaction.user.id)
        if link is None:
            raise ValueError("No linked Torii account. Use `/link <username|id>` or pass `user` explicitly.")
        return link.torii_user_id

    def _safe_embed(self, title: str, color: discord.Color = discord.Color.blurple()) -> discord.Embed:
        return discord.Embed(title=title, color=color)

    @app_commands.command(name="profile", description="Show Torii profile stats for a player.")
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.describe(user="Torii username/id. Leave empty to use your linked account.", mode="Ruleset")
    async def profile(
        self,
        interaction: discord.Interaction,
        user: str | None = None,
        mode: str | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            identifier = await self._resolve_user_identifier(interaction, user)
            data = await self.bot.api.get_user(identifier, mode=mode)
        except ValueError as exc:
            await self._send_error(interaction, str(exc))
            return
        except (ToriiApiUnauthorized, ToriiApiError) as exc:
            await self._send_error(interaction, str(exc))
            return

        stats = data.get("statistics") or {}
        chosen_mode = mode or data.get("playmode") or self.bot.settings.default_mode
        embed = self._safe_embed(f"{data.get('username', 'Unknown')} - {mode_display_name(chosen_mode)}")
        embed.url = f"{self.bot.settings.torii_web_base_url}/users/{data.get('id')}"
        avatar_url = data.get("avatar_url")
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        country = data.get("country") or {}

        embed.add_field(name="PP", value=format_number(stats.get("pp")), inline=True)
        embed.add_field(name="Global Rank", value=f"#{format_number(stats.get('global_rank'))}", inline=True)
        embed.add_field(name="Country Rank", value=f"#{format_number(stats.get('country_rank'))}", inline=True)
        embed.add_field(name="Accuracy", value=format_accuracy(stats.get("hit_accuracy")), inline=True)
        embed.add_field(name="Play Count", value=format_number(stats.get("play_count")), inline=True)
        embed.add_field(name="Ranked Score", value=format_number(stats.get("ranked_score")), inline=True)
        if country.get("name"):
            embed.set_footer(text=f"{country.get('name')} ({country.get('code', '??')})")

        await interaction.followup.send(embed=embed)

    def _score_line(self, idx: int, score: dict) -> str:
        beatmap = score.get("beatmap") or {}
        beatmapset = beatmap.get("beatmapset") or {}
        artist = beatmapset.get("artist") or "Unknown Artist"
        title = beatmapset.get("title") or "Unknown Title"
        version = beatmap.get("version") or "Unknown Diff"
        rank = score.get("rank") or "?"
        mods = format_mods(score.get("mods"))
        score_id = score.get("id") or "?"
        return (
            f"`#{idx:02}` **{rank}** {format_pp(score.get('pp'))} • {format_accuracy(score.get('accuracy'))} • "
            f"`{mods}`\n"
            f"[{artist} - {title} [{version}]]({self.bot.api.score_url(score_id)})"
        )

    @staticmethod
    def _relative_time(value: str | None) -> str:
        if not value:
            return "unknown"
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - dt
            seconds = max(0, int(delta.total_seconds()))
            if seconds < 60:
                return f"{seconds}s ago"
            if seconds < 3600:
                return f"{seconds // 60}m ago"
            if seconds < 86400:
                return f"{seconds // 3600}h ago"
            return f"{seconds // 86400}d ago"
        except Exception:
            return "unknown"

    @staticmethod
    def _rank_display(rank: str | None) -> str:
        value = (rank or "?").upper()
        return {
            "XH": "SS+",
            "X": "SS",
            "SH": "S+",
            "S": "S",
            "A": "A",
            "B": "B",
            "C": "C",
            "D": "D",
            "F": "F",
        }.get(value, value)

    @staticmethod
    def _miss_count(score: dict) -> int:
        stats = score.get("statistics") or {}
        for key in ("miss", "count_miss", "countMiss"):
            value = stats.get(key)
            if isinstance(value, int):
                return value
        return 0

    def _recent_score_field(self, idx: int, score: dict) -> tuple[str, str]:
        beatmap = score.get("beatmap") or {}
        beatmapset = beatmap.get("beatmapset") or {}
        artist = beatmapset.get("artist") or "Unknown Artist"
        title = beatmapset.get("title") or "Unknown Title"
        version = beatmap.get("version") or "Unknown Diff"
        sr = beatmap.get("difficulty_rating")
        sr_text = f"{float(sr):.2f}*" if isinstance(sr, (float, int)) else "?"
        rank = self._rank_display(score.get("rank"))
        mods = format_mods(score.get("mods"))
        score_id = score.get("id") or "?"
        combo = format_number(score.get("max_combo"))
        max_combo = format_number(beatmap.get("max_combo"))
        total_score = format_number(score.get("total_score"))
        misses = self._miss_count(score)
        ago = self._relative_time(score.get("ended_at") or score.get("created_at"))

        name = f"#{idx:02} {rank}  {format_pp(score.get('pp'))}  {format_accuracy(score.get('accuracy'))}  +{mods}"
        value = (
            f"[{artist} - {title} [{version}]]({self.bot.api.score_url(score_id)})\n"
            f"`{total_score}` | `{combo}x/{max_combo}x` | `{misses}m` | `{sr_text}` | `{ago}`"
        )
        return name, value

    @staticmethod
    def _seconds_to_mmss(value: int | float | None) -> str:
        if value is None:
            return "?:??"
        total = max(0, int(value))
        minutes = total // 60
        seconds = total % 60
        return f"{minutes:02}:{seconds:02}"

    def _recent_single_description(self, score: dict, user_data: dict) -> str:
        beatmap = score.get("beatmap") or {}
        beatmapset = beatmap.get("beatmapset") or {}
        artist = beatmapset.get("artist") or "Unknown Artist"
        title = beatmapset.get("title") or "Unknown Title"
        version = beatmap.get("version") or "Unknown Diff"
        sr = beatmap.get("difficulty_rating")
        sr_text = f"{float(sr):.2f}*" if isinstance(sr, (float, int)) else "?"
        rank = self._rank_display(score.get("rank"))
        mods = format_mods(score.get("mods"))
        total_score = format_number(score.get("total_score"))
        acc = format_accuracy(score.get("accuracy"))
        pp = format_pp(score.get("pp"))
        ago = self._relative_time(score.get("ended_at") or score.get("created_at"))
        combo = format_number(score.get("max_combo"))
        max_combo = format_number(beatmap.get("max_combo"))
        misses = self._miss_count(score)
        stats = user_data.get("statistics") or {}
        length = self._seconds_to_mmss(beatmap.get("total_length") or beatmap.get("hit_length"))
        cs = beatmap.get("cs", "?")
        ar = beatmap.get("ar", "?")
        od = beatmap.get("accuracy", "?")
        hp = beatmap.get("drain", "?")

        return (
            f"**[{artist} - {title} [{version}]]({self.bot.api.score_url(score.get('id') or '?')})**  `[{sr_text}]`\n"
            f"**{rank}** `+{mods}`  **{total_score}**  **{acc}**  `{ago}`\n"
            f"**{pp}**  •  `{combo}x/{max_combo}x`  •  `{misses}m`\n"
            f"`{length}`  •  `CS {cs}`  `AR {ar}`  `OD {od}`  `HP {hp}`\n"
            f"User PP: **{format_number(stats.get('pp'))}**  •  Rank: **#{format_number(stats.get('global_rank'))}**"
        )

    async def _enrich_scores_metadata(self, scores: list[dict]) -> None:
        beatmap_ids: list[int] = []
        for score in scores:
            beatmap = score.get("beatmap") or {}
            beatmapset = beatmap.get("beatmapset") or {}
            if beatmapset.get("artist") and beatmapset.get("title"):
                continue
            beatmap_id = beatmap.get("id")
            if isinstance(beatmap_id, int):
                beatmap_ids.append(beatmap_id)

        if not beatmap_ids:
            return

        unique_ids = list(dict.fromkeys(beatmap_ids))
        results = await asyncio.gather(
            *(self.bot.api.get_beatmap(beatmap_id) for beatmap_id in unique_ids),
            return_exceptions=True,
        )
        beatmap_lookup: dict[int, dict] = {}
        for beatmap_id, result in zip(unique_ids, results):
            if isinstance(result, dict):
                beatmap_lookup[beatmap_id] = result

        for score in scores:
            beatmap = score.get("beatmap") or {}
            beatmap_id = beatmap.get("id")
            if not isinstance(beatmap_id, int):
                continue
            fetched = beatmap_lookup.get(beatmap_id)
            if not fetched:
                continue
            score["beatmap"] = {
                **fetched,
                **beatmap,
                "beatmapset": fetched.get("beatmapset") or beatmap.get("beatmapset") or {},
            }

    @app_commands.command(name="top", description="Show top plays for a user.")
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.describe(
        user="Torii username/id. Leave empty to use your linked account.",
        mode="Ruleset",
        limit="How many scores to show (1-10)",
    )
    async def top(
        self,
        interaction: discord.Interaction,
        user: str | None = None,
        mode: str | None = None,
        limit: app_commands.Range[int, 1, 10] = 5,
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            identifier = await self._resolve_user_identifier(interaction, user)
            user_data = await self.bot.api.get_user(identifier, mode=mode)
            scores = await self.bot.api.get_user_scores(
                int(user_data["id"]),
                "best",
                mode=mode,
                limit=limit,
            )
        except ValueError as exc:
            await self._send_error(interaction, str(exc))
            return
        except (ToriiApiUnauthorized, ToriiApiError) as exc:
            await self._send_error(interaction, str(exc))
            return

        chosen_mode = mode or user_data.get("playmode") or self.bot.settings.default_mode
        embed = self._safe_embed(f"Top Plays - {user_data.get('username')} ({mode_display_name(chosen_mode)})")
        if not scores:
            embed.description = "No scores found."
        else:
            await self._enrich_scores_metadata(scores)
            embed.description = "\n\n".join(self._score_line(i, score) for i, score in enumerate(scores, start=1))
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="recent", description="Show recent plays for a user (24h window).")
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.describe(
        user="Torii username/id. Leave empty to use your linked account.",
        mode="Ruleset",
        limit="How many scores to show (1-10)",
        include_fails="Include failed scores",
    )
    async def recent(
        self,
        interaction: discord.Interaction,
        user: str | None = None,
        mode: str | None = None,
        limit: app_commands.Range[int, 1, 10] = 5,
        include_fails: bool = False,
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            identifier = await self._resolve_user_identifier(interaction, user)
            user_data = await self.bot.api.get_user(identifier, mode=mode)
            scores = await self.bot.api.get_user_scores(
                int(user_data["id"]),
                "recent",
                mode=mode,
                include_fails=include_fails,
                limit=limit,
            )
        except ValueError as exc:
            await self._send_error(interaction, str(exc))
            return
        except (ToriiApiUnauthorized, ToriiApiError) as exc:
            await self._send_error(interaction, str(exc))
            return

        chosen_mode = mode or user_data.get("playmode") or self.bot.settings.default_mode
        embed = self._safe_embed(f"Recent Plays - {user_data.get('username')} ({mode_display_name(chosen_mode)})")
        if not scores:
            embed.description = "No recent plays in the last 24h."
        else:
            await self._enrich_scores_metadata(scores)
            latest = scores[0]
            embed.description = self._recent_single_description(latest, user_data)
            beatmapset = ((latest.get("beatmap") or {}).get("beatmapset") or {})
            covers = beatmapset.get("covers") or {}
            cover_url = covers.get("card") or covers.get("list") or covers.get("cover")
            if cover_url:
                embed.set_image(url=cover_url)
            embed.set_footer(text="Showing latest play")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="score", description="Show one score by id or score URL.")
    @app_commands.describe(score="Score id or Torii score URL")
    async def score(self, interaction: discord.Interaction, score: str) -> None:
        await interaction.response.defer(thinking=True)
        score_id = extract_score_id(score)
        if score_id is None:
            await self._send_error(interaction, "Invalid score id/URL.")
            return
        try:
            data = await self.bot.api.get_score(score_id)
        except (ToriiApiUnauthorized, ToriiApiError) as exc:
            await self._send_error(interaction, str(exc))
            return

        user = data.get("user") or {}
        beatmap = data.get("beatmap") or {}
        beatmapset = beatmap.get("beatmapset") or {}
        title = f"{beatmapset.get('artist', '?')} - {beatmapset.get('title', '?')} [{beatmap.get('version', '?')}]"
        embed = self._safe_embed(title)
        embed.url = self.bot.api.score_url(data.get("id", score_id))
        embed.add_field(name="Player", value=f"{user.get('username', 'Unknown')} (`{user.get('id', '?')}`)", inline=False)
        embed.add_field(name="Rank", value=str(data.get("rank", "?")), inline=True)
        embed.add_field(name="PP", value=format_pp(data.get("pp")), inline=True)
        embed.add_field(name="Accuracy", value=format_accuracy(data.get("accuracy")), inline=True)
        embed.add_field(name="Mods", value=format_mods(data.get("mods")), inline=True)
        embed.add_field(name="Score", value=format_number(data.get("total_score")), inline=True)
        embed.add_field(name="Max Combo", value=format_number(data.get("max_combo")), inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="beatmap", description="Show beatmap info and leaderboard preview.")
    @app_commands.choices(mode=MODE_CHOICES, leaderboard_type=LEADERBOARD_TYPE_CHOICES)
    @app_commands.describe(
        beatmap="Beatmap id or URL",
        mode="Ruleset to fetch leaderboard",
        leaderboard_type="Leaderboard type",
        limit="How many leaderboard entries (1-10)",
    )
    async def beatmap(
        self,
        interaction: discord.Interaction,
        beatmap: str,
        mode: str | None = None,
        leaderboard_type: str = "global",
        limit: app_commands.Range[int, 1, 10] = 5,
    ) -> None:
        await interaction.response.defer(thinking=True)
        beatmap_id = extract_beatmap_id(beatmap)
        if beatmap_id is None:
            await self._send_error(interaction, "Invalid beatmap id/URL.")
            return
        chosen_mode = mode or self.bot.settings.default_mode
        try:
            beatmap_data = await self.bot.api.get_beatmap(beatmap_id)
            scores = await self.bot.api.get_beatmap_scores(
                beatmap_id,
                mode=chosen_mode,
                leaderboard_type=leaderboard_type,
                limit=limit,
            )
        except (ToriiApiUnauthorized, ToriiApiError) as exc:
            await self._send_error(interaction, str(exc))
            return

        beatmapset = beatmap_data.get("beatmapset") or {}
        title = (
            f"{beatmapset.get('artist', '?')} - {beatmapset.get('title', '?')} "
            f"[{beatmap_data.get('version', '?')}]"
        )
        embed = self._safe_embed(title)
        embed.url = f"{self.bot.settings.torii_web_base_url}/beatmapsets/{beatmapset.get('id', '')}#osu/{beatmap_id}"
        embed.add_field(name="Stars", value=f"{beatmap_data.get('difficulty_rating', '?')}", inline=True)
        embed.add_field(name="BPM", value=f"{beatmap_data.get('bpm', '?')}", inline=True)
        embed.add_field(name="Mode", value=mode_display_name(chosen_mode), inline=True)

        top_scores = scores.get("scores") or []
        if top_scores:
            lines: list[str] = []
            for i, score_data in enumerate(top_scores[:limit], start=1):
                player = (score_data.get("user") or {}).get("username", "Unknown")
                lines.append(
                    f"`#{i:02}` **{player}** • {format_pp(score_data.get('pp'))} • "
                    f"{format_accuracy(score_data.get('accuracy'))}"
                )
            embed.add_field(name=f"Top {min(limit, len(top_scores))}", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Top", value="No leaderboard entries.", inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="rankings", description="Show Torii global rankings.")
    @app_commands.choices(mode=MODE_CHOICES, sort=RANK_SORT_CHOICES)
    @app_commands.describe(mode="Ruleset", sort="Sort type", page="Ranking page")
    async def rankings(
        self,
        interaction: discord.Interaction,
        mode: str | None = None,
        sort: str = "performance",
        page: app_commands.Range[int, 1, 200] = 1,
    ) -> None:
        await interaction.response.defer(thinking=True)
        chosen_mode = mode or self.bot.settings.default_mode
        try:
            data = await self.bot.api.get_rankings(mode=chosen_mode, sort=sort, page=page)
        except (ToriiApiUnauthorized, ToriiApiError) as exc:
            await self._send_error(interaction, str(exc))
            return

        ranking = data.get("ranking") or []
        embed = self._safe_embed(f"Rankings - {mode_display_name(chosen_mode)} ({sort})")
        if not ranking:
            embed.description = "No ranking data returned."
            await interaction.followup.send(embed=embed)
            return

        lines: list[str] = []
        base_rank = (page - 1) * 50
        for index, item in enumerate(ranking[:10], start=1):
            user = item.get("user") or {}
            username = user.get("username", "Unknown")
            pp = item.get("pp") if sort == "performance" else item.get("ranked_score")
            value = format_number(pp)
            lines.append(f"`#{base_rank + index:03}` **{username}** • {value}")
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Page {page} • Total: {format_number(data.get('total'))}")
        await interaction.followup.send(embed=embed)


async def setup(bot: ToriiBot) -> None:
    await bot.add_cog(OsuStatsCog(bot))
