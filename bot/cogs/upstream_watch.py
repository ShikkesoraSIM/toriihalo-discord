"""Upstream-watch cog.

Polls ``ppy/osu`` **releases** (not master) for source-level changes
that would block a Torii rebase, and pings the mod channel when one is
detected. The first (and currently only) thing we watch is the realm
``schema_version`` constant in ``osu.Game/Database/RealmAccess.cs``.

Why releases instead of master
------------------------------
A PR landing on master that bumps the schema doesn't actually ship the
new layout to anyone — it sits on master until peppy tags a release
(``-lazer`` or ``-tachyon``) that builds from that commit. Torii
rebases from upstream release points, not master, so what matters to
us is "when did a build that contains v52 actually go out to users".
Watching master would fire days (sometimes weeks) before any user has
a DB at the new schema, which is just noise.

Mechanics
---------
1. GET ``api.github.com/repos/ppy/osu/releases?per_page=1`` to find
   the most recent release across both streams (lazer + tachyon, in
   the order GitHub serves them — newest first).
2. GET the raw ``RealmAccess.cs`` *at that release's tag* (not master).
3. Parse the ``schema_version`` integer.
4. Compare with what we recorded last time. Alert on a strict
   increase.

Why a dedicated cog instead of a GitHub-side webhook
----------------------------------------------------
A webhook on ``ppy/osu`` would require admin access we don't have, and
GitHub release webhooks don't carry file content. Polling is dumb-simple,
has zero coupling to upstream's processes, and the cadence is gentle
(every 6 h by default) so the GitHub anonymous-API rate limit (60/h)
isn't even close to touched.

State persistence
-----------------
We store the highest schema_version we've alerted on in ``bot_kv`` under
``upstream_watch.realm_schema_last_seen``. First run records the
current value silently — we only fire the alert when the integer
strictly increases between two polls. Updates to ``bot_kv`` happen
*after* the alert posts successfully, so a failed post will retry on
the next tick (rather than silently swallowing the alert).

Failure modes
-------------
* GitHub API 5xx / network error / rate-limit: logged at warning, no
  DB write, no alert. Retries on the next tick.
* Empty / malformed releases response: same — silent no-op + log.
* Regex doesn't find the constant (upstream renamed/restructured):
  logged at warning, no DB write.
* Channel unresolvable: logged once, alert skipped — but kv is still
  updated so we don't spam the log every cycle.
* Bot restart mid-transition: the last-seen value is already in
  ``bot_kv`` so we don't double-alert on the same bump.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord
import httpx
from discord.ext import commands, tasks


logger = logging.getLogger(__name__)


# GitHub API: latest release (any stream, lazer / tachyon / prerelease).
# `per_page=1` gives just the newest entry — GitHub's response order is
# already newest-first by published-date.
GITHUB_API_LATEST_RELEASES_URL = "https://api.github.com/repos/ppy/osu/releases?per_page=1"

# Per-tag raw content of the realm schema file. Tag is substituted in
# at request time so we always read what shipped at the release point,
# not whatever is on master.
UPSTREAM_REALM_RAW_TEMPLATE = (
    "https://raw.githubusercontent.com/ppy/osu/{tag}/osu.Game/Database/RealmAccess.cs"
)

# Torii's own copy. We deliberately use master here — the question we
# answer in the alert is "where are WE right now", which is whatever
# is on master (i.e. what we'd ship if we tagged a release today). If
# you'd rather compare against Torii's latest tagged release, swap the
# `/master/` segment for a release-API call (same pattern as upstream).
TORII_REALM_URL = (
    "https://raw.githubusercontent.com/ShikkesoraSIM/torii-osu/master/osu.Game/Database/RealmAccess.cs"
)

# Static links surfaced in the alert embed (the per-release link is
# built dynamically using the tag we found at poll time).
UPSTREAM_RELEASES_URL = "https://github.com/ppy/osu/releases"
UPSTREAM_REALM_RECENT_COMMITS_URL = (
    "https://github.com/ppy/osu/commits/master/osu.Game/Database/RealmAccess.cs"
)

# Matches the canonical declaration ``private const int schema_version =
# N;`` regardless of intervening whitespace / qualifiers. Anchored on
# the identifier so a stray ``schema_version`` mention elsewhere in the
# file (e.g. inside an XML-doc) wouldn't accidentally match — the
# ``const int`` bit makes it a unique syntactic shape.
SCHEMA_VERSION_RE = re.compile(
    r"\bconst\s+int\s+schema_version\s*=\s*(?P<n>\d+)\s*;",
)

# bot_kv key. Namespaced so other cogs don't collide.
KV_LAST_SEEN_KEY = "upstream_watch.realm_schema_last_seen"


class UpstreamWatchCog(commands.Cog):
    """Polls upstream ppy/osu **releases** for breaking-change canaries."""

    def __init__(self, bot) -> None:
        self.bot = bot
        # discord.py refuses to register a tasks.loop with a 0 / negative
        # interval, and the actual cadence is read from settings at
        # runtime — initialise with a placeholder that's just "alive" and
        # gets corrected on the first tick.
        self.poll_upstream.start()
        self._channel_warned = False

    def cog_unload(self) -> None:
        self.poll_upstream.cancel()

    # ---- Channel resolution (mirrors ModAlertsCog) ------------------

    async def _resolve_channel(self) -> discord.TextChannel | None:
        # Dedicated upstream-watch channel takes priority, falls back
        # to the mod-alert channel so users with one combined channel
        # don't have to configure twice.
        channel_id = (
            self.bot.settings.upstream_watch_channel_id
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
                        "upstream_watch: failed to fetch channel %s: %s",
                        channel_id, exc,
                    )
                    self._channel_warned = True
                return None

        if isinstance(channel, discord.TextChannel):
            self._channel_warned = False
            return channel
        if not self._channel_warned:
            logger.warning(
                "upstream_watch: configured channel %s is not a text channel",
                channel_id,
            )
            self._channel_warned = True
        return None

    # ---- Polling loop ------------------------------------------------

    @tasks.loop(seconds=21600.0)
    async def poll_upstream(self) -> None:
        # Pick up live config changes — same pattern as mod_alerts.
        configured = max(60.0, float(self.bot.settings.upstream_watch_interval_seconds))
        if abs(self.poll_upstream.seconds - configured) > 0.001:
            self.poll_upstream.change_interval(seconds=configured)

        # 1. What's the most recent release tag?
        release = await self._fetch_latest_release()
        if release is None:
            return  # logged in helper

        tag = release.get("tag_name")
        release_html_url = release.get("html_url") or UPSTREAM_RELEASES_URL
        release_published = release.get("published_at")
        if not isinstance(tag, str) or not tag:
            logger.warning("upstream_watch: release entry missing tag_name: %r", release)
            return

        # 2. What schema_version does that release ship?
        realm_url = UPSTREAM_REALM_RAW_TEMPLATE.format(tag=tag)
        upstream_version = await self._fetch_schema_version(realm_url)
        if upstream_version is None:
            return

        # Companion fetch for the embed — best-effort, errors don't
        # block the alert.
        torii_version = await self._fetch_schema_version(TORII_REALM_URL, soft=True)

        # 3. Compare with what we recorded last time.
        last_seen_raw = await self.bot.db.kv_get(KV_LAST_SEEN_KEY)
        last_seen: int | None
        try:
            last_seen = int(last_seen_raw) if last_seen_raw is not None else None
        except ValueError:
            # Corrupted row — reset rather than crash. Worst case we
            # miss exactly one alert.
            logger.warning(
                "upstream_watch: bot_kv value %r for %s is not an int; resetting",
                last_seen_raw, KV_LAST_SEEN_KEY,
            )
            last_seen = None

        # First run: record silently. No alert because we have nothing
        # to compare against. The schema in the current latest release
        # is the baseline — the next bump that ships in a release will
        # fire the first alert.
        if last_seen is None:
            await self.bot.db.kv_set(KV_LAST_SEEN_KEY, str(upstream_version))
            logger.info(
                "upstream_watch: first poll, baseline schema_version=%d from release %s",
                upstream_version, tag,
            )
            return

        # No bump → no-op. Most polls take this branch (releases ship
        # weekly-ish but schema bumps are months apart).
        if upstream_version == last_seen:
            return

        # Schema decreased (release tags an older commit, or peppy
        # reverted). Record + log, no @here.
        if upstream_version < last_seen:
            logger.warning(
                "upstream_watch: release %s ships schema_version=%d, "
                "lower than previously seen %d (revert / cherry-pick?)",
                tag, upstream_version, last_seen,
            )
            await self.bot.db.kv_set(KV_LAST_SEEN_KEY, str(upstream_version))
            return

        # Bump path. Resolve channel + post.
        channel = await self._resolve_channel()
        if channel is None:
            # No channel — record the new value anyway so we don't
            # spam the log every cycle waiting for a config.
            logger.warning(
                "upstream_watch: release %s bumps schema %d → %d but no channel configured",
                tag, last_seen, upstream_version,
            )
            await self.bot.db.kv_set(KV_LAST_SEEN_KEY, str(upstream_version))
            return

        try:
            embed = self._build_embed(
                old_version=last_seen,
                new_version=upstream_version,
                torii_version=torii_version,
                tag=tag,
                release_html_url=release_html_url,
                release_published=release_published,
            )
            mention = "@here" if self.bot.settings.upstream_watch_mention_here else None
            await channel.send(
                content=mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(everyone=True),
            )
            await self.bot.db.kv_set(KV_LAST_SEEN_KEY, str(upstream_version))
            logger.info(
                "upstream_watch: alerted on release %s shipping schema bump %d → %d",
                tag, last_seen, upstream_version,
            )
        except Exception as exc:
            # If posting failed, DO NOT update kv — we want the next
            # tick to retry the same alert.
            logger.exception("upstream_watch: failed to post bump alert: %s", exc)

    @poll_upstream.before_loop
    async def before_poll_upstream(self) -> None:
        await self.bot.wait_until_ready()

    # ---- HTTP helpers -----------------------------------------------

    async def _fetch_latest_release(self) -> dict[str, Any] | None:
        """Return the dict for the most recent ppy/osu release (any stream).

        Uses the listing endpoint with ``per_page=1`` rather than the
        ``/releases/latest`` endpoint, because the latter filters out
        prereleases and we want to see ``-tachyon`` builds too (they're
        public, end-users do install them, the on-disk schema in them
        absolutely matters to us).
        """
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": "torii-discord-bot/upstream-watch",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                follow_redirects=True,
            ) as client:
                resp = await client.get(GITHUB_API_LATEST_RELEASES_URL)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("upstream_watch: failed to fetch latest release: %s", exc)
            return None
        except Exception as exc:
            logger.exception("upstream_watch: unexpected error fetching releases: %s", exc)
            return None

        if not isinstance(data, list) or not data:
            logger.warning("upstream_watch: releases endpoint returned empty/malformed: %r", data)
            return None

        entry = data[0]
        if not isinstance(entry, dict):
            logger.warning("upstream_watch: release entry isn't a dict: %r", entry)
            return None
        return entry

    async def _fetch_schema_version(self, url: str, *, soft: bool = False) -> int | None:
        """Fetch the file and parse the schema_version constant.

        With ``soft=True`` (used for the Torii companion fetch) failures
        return None silently — the caller can still proceed with just
        the upstream value. With ``soft=False`` we log a warning so
        prolonged outages are visible in the bot log.
        """
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": "torii-discord-bot/upstream-watch"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                text = resp.text
        except httpx.HTTPError as exc:
            if not soft:
                logger.warning("upstream_watch: GET %s failed: %s", url, exc)
            return None
        except Exception as exc:
            if not soft:
                logger.exception("upstream_watch: unexpected error fetching %s: %s", url, exc)
            return None

        match = SCHEMA_VERSION_RE.search(text)
        if not match:
            if not soft:
                logger.warning(
                    "upstream_watch: schema_version regex didn't match for %s "
                    "(file restructured upstream?)",
                    url,
                )
            return None

        try:
            return int(match.group("n"))
        except ValueError:
            if not soft:
                logger.warning("upstream_watch: parsed non-int from %s", url)
            return None

    # ---- Embed builder ----------------------------------------------

    def _build_embed(
        self,
        *,
        old_version: int,
        new_version: int,
        torii_version: int | None,
        tag: str,
        release_html_url: str,
        release_published: str | None,
    ) -> discord.Embed:
        delta = new_version - old_version
        title = (
            f"🚨 ppy/osu shipped a realm schema bump in {tag}"
            if delta == 1
            else f"🚨 ppy/osu shipped a realm schema bump (+{delta}) in {tag}"
        )

        description_lines = [
            f"`schema_version`: **{old_version}** → **{new_version}**",
            f"Release: [{tag}]({release_html_url})",
        ]
        if release_published:
            description_lines.append(f"Published: `{release_published}`")
        description_lines.extend([
            "",
            "**What this means:** this is the first **release** to ship the new "
            "on-disk schema. Any Torii client opening a DB that's been touched "
            "by an upstream build at this tag will need a migration to read it. "
            "If we rebase onto this release, we ship the new schema and need to "
            "handle the migration ourselves.",
            "",
            "**Next steps:**",
            "- Diff `RealmAccess.cs` between previous schema and this one to see what fields/indexes changed.",
            "- Decide migration vs. downgrade strategy before the next rebase.",
            "- If we already have a `RealmDowngrader` slot ready, queue it up.",
        ])
        if torii_version is not None:
            description_lines.append("")
            description_lines.append(
                f"Torii local `schema_version` (master): **{torii_version}** "
                f"(gap: {new_version - torii_version})"
            )

        embed = discord.Embed(
            title=title,
            description="\n".join(description_lines),
            color=discord.Color.red(),
        )
        realm_at_tag_url = (
            f"https://github.com/ppy/osu/blob/{tag}/osu.Game/Database/RealmAccess.cs"
        )
        embed.add_field(
            name="Links",
            value=(
                f"[Release page]({release_html_url})\n"
                f"[RealmAccess.cs @ {tag}]({realm_at_tag_url})\n"
                f"[Recent commits to RealmAccess.cs]({UPSTREAM_REALM_RECENT_COMMITS_URL})\n"
                f"[All upstream releases]({UPSTREAM_RELEASES_URL})"
            ),
            inline=False,
        )
        embed.set_footer(
            text=(
                f"upstream-watch · polled every {int(self.poll_upstream.seconds)}s · "
                f"src: latest release across lazer+tachyon"
            )
        )
        return embed


async def setup(bot) -> None:
    await bot.add_cog(UpstreamWatchCog(bot))
