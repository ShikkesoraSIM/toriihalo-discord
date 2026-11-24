import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from bot.cogs.osu import OsuStatsCog
from bot.score_browser import RecentScoresView
from bot.torii_api import ToriiApiError


def score(index=1):
    return dict(id=index, pp=123.45, accuracy=0.9876, max_combo=300, total_score=987654,
                rank="A", ended_at="2026-11-24T01:00:00Z", mods=[dict(acronym="DT", settings=dict(speed_change=1.2))],
                statistics=dict(great=300, ok=7, meh=1, miss=2),
                beatmap=dict(id=50, version="Insane", difficulty_rating=5.3, max_combo=500, bpm=180, cs=4, ar=9, accuracy=8, drain=6,
                             beatmapset=dict(artist="Artist", title="Song", covers=dict(card="https://example.com/cover.jpg"))))


def interaction(owner=7):
    return SimpleNamespace(user=SimpleNamespace(id=owner), response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()), edit_original_response=AsyncMock())


def view(count=12, mode="osu"):
    return RecentScoresView(7, dict(id=10, username="Player_Name"), [score(i) for i in range(1, count + 1)], mode, "https://lazer.shikkesora.com")


def test_navigation_and_layout():
    async def run():
        browser = view()
        event = interaction()
        assert browser.previous.disabled
        assert browser.position.label == "1 / 12"
        await browser.next.callback(event)
        assert browser.index == 1
        assert browser.score_link.url.endswith("/scores/2")
        await browser.layout.callback(event)
        assert browser.position.label == "1-5 / 12"
        assert len(browser.embed().fields) == 5
        assert browser.score_link.disabled
        await browser.next.callback(event)
        assert browser.index == 5
        await browser.next.callback(event)
        assert browser.index == 10
        assert browser.next.disabled
        assert len(browser.embed().fields) == 2
        await browser.next.callback(event)
        assert browser.index == 10
        await browser.previous.callback(event)
        assert browser.index == 5
        await browser.layout.callback(event)
        assert browser.position.label == "6 / 12"
        assert not browser.score_link.disabled
        assert event.edit_original_response.await_count == 7
        browser.stop()
    asyncio.run(run())


def test_access_timeout_and_one_score():
    async def run():
        browser = view(1)
        assert browser.previous.disabled and browser.next.disabled
        stranger = interaction(8)
        assert not await browser.interaction_check(stranger)
        stranger.response.send_message.assert_awaited_once()
        assert await browser.interaction_check(interaction())
        browser.message = SimpleNamespace(edit=AsyncMock())
        await browser.on_timeout()
        assert all(item.disabled for item in browser.children if item.style != discord.ButtonStyle.link)
        assert not browser.score_link.disabled
        browser.message.edit.assert_awaited_once()
        browser.stop()
    asyncio.run(run())


def test_embed_uses_server_pp_and_base_map_attributes():
    async def run():
        browser = view(1)
        embed = browser.embed()
        fields = {field.name: field.value for field in embed.fields}
        assert fields["Performance"] == "**123.45pp**"
        assert fields["Accuracy"] == "98.76%"
        assert "DT 1.2x" in embed.description
        assert "NM" in embed.description and "Map (NM)" in fields
        assert "300: **300**" in fields["Judgements"]
        assert "Miss: **2**" in fields["Judgements"]
        assert embed.author.name.startswith("Player_Name")
        assert embed.image.url == "https://example.com/cover.jpg"
        assert len(embed) <= 6000
        browser.stop()
    asyncio.run(run())


@pytest.mark.parametrize("mode,label,key", [("mania", "MAX", "perfect"), ("taikorx", "300", "great"), ("fruitsrx", "Tiny", "small_tick_hit")])
def test_ruleset_judgements(mode, label, key):
    async def run():
        browser = view(1, mode)
        browser.scores[0]["statistics"] = {key: 123}
        values = {f.name: f.value for f in browser.embed().fields}
        assert f"{label}: **123**" in values["Judgements"]
        browser.stop()
    asyncio.run(run())


def test_missing_metadata_and_long_text_fit():
    async def run():
        with pytest.raises(ValueError):
            RecentScoresView(7, {}, [], "osu", "https://example.com")
        browser = view(1)
        browser.scores = [dict(id=None, pp=None, accuracy=None, beatmap=dict(beatmapset=dict(title="x" * 5000, covers=dict(card="http://example.com/a"))))]
        embed = browser.embed()
        assert len(embed.title) <= 256
        assert not embed.image.url
        assert embed.fields[0].value == "**--**"
        browser._sync_controls()
        assert browser.score_link.disabled
        await browser.layout.callback(interaction())
        assert len(browser.embed().fields[0].value) < 1024
        browser.stop()
    asyncio.run(run())


def fake_bot():
    return SimpleNamespace(api=SimpleNamespace(get_beatmap=AsyncMock(), get_user=AsyncMock(return_value=dict(id=10, username="Player", playmode="osu")),
                                               get_user_scores=AsyncMock()),
                           db=SimpleNamespace(get_linked_account=AsyncMock(return_value=SimpleNamespace(torii_user_id=10))),
                           settings=SimpleNamespace(default_mode="osu", torii_web_base_url="https://lazer.shikkesora.com"))


def test_recent_loading_respects_link_mode_and_fail_filter():
    async def run():
        bot = fake_bot()
        bot.api.get_user_scores.return_value = [score()]
        cog = OsuStatsCog(bot)
        browser = await cog._recent_browser(7, None, "mania", 10, True)
        bot.db.get_linked_account.assert_awaited_once_with(7)
        bot.api.get_user_scores.assert_awaited_once_with(10, "recent", mode="mania", limit=10, include_fails=True)
        assert browser.mode == "mania"
        bot.api.get_beatmap.assert_not_awaited()
        browser.stop()
        bot.api.get_user_scores.return_value = []
        assert await cog._recent_browser(7, "Other", None, 10, False) is None
        with pytest.raises(ValueError):
            await cog._recent_browser(7, None, "made_up", 10, False)
    asyncio.run(run())


def test_metadata_is_deduplicated_cached_and_optional():
    async def run():
        bot = fake_bot()
        bot.api.get_beatmap.return_value = score()["beatmap"]
        cog = OsuStatsCog(bot)
        missing = [dict(beatmap=dict(id=50)), dict(beatmap=dict(id=50))]
        await cog._enrich_scores_metadata(missing)
        assert missing[0]["beatmap"]["beatmapset"]["title"] == "Song"
        await cog._enrich_scores_metadata([dict(beatmap=dict(id=50))])
        bot.api.get_beatmap.assert_awaited_once_with(50)
        bot.api.get_beatmap.side_effect = ToriiApiError("unavailable")
        await cog._enrich_scores_metadata([dict(beatmap=dict(id=51))])
        assert 51 not in cog._metadata_cache
        bot.api.get_beatmap.side_effect = None
        cog._metadata_cache[50] = (0, {})
        await cog._enrich_scores_metadata([dict(beatmap=dict(id=50))])
        assert bot.api.get_beatmap.await_count == 3
        for i in range(300):
            await cog._beatmap_metadata(i + 100)
        assert len(cog._metadata_cache) == 256
    asyncio.run(run())


def test_navigation_is_serialized():
    async def run():
        browser = view()
        events = [interaction() for _ in range(4)]
        await asyncio.gather(*(browser.next.callback(event) for event in events))
        assert browser.index == 4
        assert browser.score_link.url.endswith("/scores/5")
        browser.stop()
    asyncio.run(run())


def test_metadata_concurrency_is_bounded():
    async def run():
        bot = fake_bot()
        active = 0
        peak = 0

        async def fetch(beatmap_id):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            return score()["beatmap"]

        bot.api.get_beatmap.side_effect = fetch
        cog = OsuStatsCog(bot)
        await cog._enrich_scores_metadata([dict(beatmap=dict(id=i)) for i in range(20)])
        assert peak <= 3
    asyncio.run(run())


def test_rs_command_success_empty_and_sanitized_error():
    async def run():
        bot = fake_bot()
        cog = OsuStatsCog(bot)
        ctx = SimpleNamespace(author=SimpleNamespace(id=7), defer=AsyncMock(), send=AsyncMock())
        bot.api.get_user_scores.return_value = [score()]
        await cog.rs.callback(cog, ctx)
        browser = ctx.send.call_args.kwargs["view"]
        assert browser.message is ctx.send.return_value
        assert ctx.send.call_args.kwargs["allowed_mentions"].everyone is False
        browser.stop()
        ctx.send.reset_mock()
        bot.api.get_user_scores.return_value = []
        await cog.rs.callback(cog, ctx)
        assert "No recent plays" in ctx.send.call_args.args[0]
        ctx.send.reset_mock()
        bot.api.get_user.side_effect = ToriiApiError("sensitive server detail")
        await cog.rs.callback(cog, ctx)
        assert "sensitive" not in ctx.send.call_args.args[0]
        assert "try again" in ctx.send.call_args.args[0].lower()
    asyncio.run(run())

