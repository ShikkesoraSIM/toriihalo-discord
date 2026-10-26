import asyncio
import datetime
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from bot.cogs.owner_ping import CONFIG_KEY, DECAY_SECONDS, OwnerPingGuardCog, active_count, warning_text
from bot.database import BotDatabase


CONFIG = {
    "enabled": True, "guild_id": 100, "owner_id": 1, "rule_id": 200,
    "log_channel_id": 300, "exempt_role_ids": [10, 11],
}


class MemoryDB:
    def __init__(self):
        self.values = {CONFIG_KEY: json.dumps(CONFIG)}

    async def kv_get(self, key):
        return self.values.get(key)

    async def kv_set(self, key, value):
        self.values[key] = value


def fixture(db=None):
    channel = SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(id=100, owner_id=1, ban=AsyncMock())
    member = SimpleNamespace(
        id=42, display_name="kit", bot=False, guild=guild, roles=[], send=AsyncMock(), timeout=AsyncMock(),
        guild_permissions=SimpleNamespace(administrator=False, manage_guild=False, manage_messages=False),
    )
    guild.fetch_member = AsyncMock(return_value=member)
    guild.get_channel_or_thread = lambda _: SimpleNamespace(name="general")
    owner = SimpleNamespace(id=1, send=AsyncMock())
    bot = SimpleNamespace(
        db=db or MemoryDB(), get_channel=lambda _: channel, fetch_channel=AsyncMock(return_value=channel),
        get_user=lambda _: owner, fetch_user=AsyncMock(return_value=owner), owner=owner,
    )
    cog = OwnerPingGuardCog(bot)
    event = SimpleNamespace(
        action=SimpleNamespace(type=discord.AutoModRuleActionType.timeout, duration=datetime.timedelta(minutes=30)),
        guild_id=100, rule_id=200, guild=guild, member=member, user_id=42, channel_id=500, message_id=None,
        content="hey <@1> question about coinflip",
    )
    return cog, event, channel


def forbidden():
    return discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "no permission")


def test_warning_text_explains_all_three_steps():
    assert "warning 1 out of 3" in warning_text(1)
    assert "second warning: 24 hour timeout, third warning: ban" in warning_text(1)
    assert "action: 24 hour timeout" in warning_text(2)
    assert "action: ban" in warning_text(3)
    assert "30 days" in warning_text(1)


def test_full_ladder_and_persistent_history(monkeypatch):
    now = [1_800_000_000.0]
    monkeypatch.setattr("bot.cogs.owner_ping.time.time", lambda: now[0])
    cog, event, channel = fixture()

    async def run():
        await cog.on_automod_action(event)
        event.member.timeout.assert_not_awaited()
        event.guild.ban.assert_not_awaited()
        now[0] += 1801
        await cog.on_automod_action(event)
        assert event.member.timeout.await_args.args[0] == datetime.timedelta(hours=24)
        now[0] += 86401
        # Un restart no tiene que borrar los avisos.
        restarted = OwnerPingGuardCog(cog.bot)
        await restarted.on_automod_action(event)
        event.guild.ban.assert_awaited_once_with(event.member, reason="owner ping: warning 3/3; 30 day inactivity reset", delete_message_seconds=0)
        state = await cog._state(100, 42)
        assert state["count"] == 3
        assert [item["status"] for item in state["history"]] == ["30 minute timeout (AutoMod)", "24 hour timeout", "banned"]
        assert channel.send.await_count == 3
        for call in channel.send.await_args_list:
            assert call.kwargs["allowed_mentions"].users is False

    asyncio.run(run())


@pytest.mark.parametrize("action", [discord.AutoModRuleActionType.block_message, discord.AutoModRuleActionType.send_alert_message])
def test_other_native_actions_do_not_add_warnings(action):
    cog, event, channel = fixture()
    event.action.type = action
    asyncio.run(cog.on_automod_action(event))
    assert len(cog.bot.db.values) == 1
    channel.send.assert_not_awaited()


@pytest.mark.parametrize("change", ["disabled", "guild", "rule", "owner", "bot", "admin", "manager", "moderator", "staff_role", "duration"])
def test_scope_and_staff_exemptions(change):
    cog, event, channel = fixture()
    if change == "disabled":
        cog.bot.db.values[CONFIG_KEY] = json.dumps({**CONFIG, "enabled": False})
    elif change == "guild":
        event.guild_id = 999
    elif change == "rule":
        event.rule_id = 999
    elif change == "owner":
        event.guild.owner_id = 999
    elif change == "bot":
        event.member.bot = True
    elif change in ("admin", "manager", "moderator"):
        name = {"admin": "administrator", "manager": "manage_guild", "moderator": "manage_messages"}[change]
        setattr(event.member.guild_permissions, name, True)
    elif change == "staff_role":
        event.member.roles = [SimpleNamespace(id=11)]
    else:
        event.action.duration = datetime.timedelta(seconds=10)
    asyncio.run(cog.on_automod_action(event))
    channel.send.assert_not_awaited()
    event.guild.ban.assert_not_awaited()
    assert len(cog.bot.db.values) == 1


def test_concurrent_duplicate_events_count_once():
    cog, event, channel = fixture()

    async def run():
        await asyncio.gather(*(cog.on_automod_action(event) for _ in range(10)))
        assert (await cog._state(100, 42))["count"] == 1
        channel.send.assert_awaited_once()

    asyncio.run(run())


def test_edited_message_is_not_counted_again(monkeypatch):
    cog, event, channel = fixture()
    now = [1_800_000_000.0]
    monkeypatch.setattr("bot.cogs.owner_ping.time.time", lambda: now[0])
    event.message_id = 700

    async def run():
        await cog.on_automod_action(event)
        now[0] += 2000
        await cog.on_automod_action(event)
        assert (await cog._state(100, 42))["count"] == 1

    asyncio.run(run())


def test_thirty_days_of_inactivity_reset_counter_but_keep_history(monkeypatch):
    cog, event, channel = fixture()
    now = [1_800_000_000.0]
    monkeypatch.setattr("bot.cogs.owner_ping.time.time", lambda: now[0])

    async def run():
        await cog.on_automod_action(event)
        now[0] += DECAY_SECONDS
        await cog.on_automod_action(event)
        state = await cog._state(100, 42)
        assert state["count"] == 1
        assert len(state["history"]) == 2
        event.member.timeout.assert_not_awaited()

    asyncio.run(run())
    assert active_count({"count": 2, "last_at": 100}, 100 + DECAY_SECONDS - 1) == 2


def test_missing_dm_does_not_prevent_record_or_escalation():
    cog, event, channel = fixture()
    event.member.send.side_effect = forbidden()

    async def run():
        await cog.on_automod_action(event)
        assert (await cog._state(100, 42))["history"][0]["dm"] == "unavailable"
        channel.send.assert_awaited_once()

    asyncio.run(run())


def test_failed_ban_is_not_logged_as_success():
    cog, event, channel = fixture()
    event.guild.ban.side_effect = forbidden()

    async def run():
        await cog._save(100, 42, {"count": 2, "last_at": time.time() - 90000, "history": []})
        await cog.on_automod_action(event)
        state = await cog._state(100, 42)
        assert "escalation failed" in state["history"][0]["status"]
        assert "native 30 minute timeout" in state["history"][0]["status"]

    asyncio.run(run())


@pytest.mark.parametrize("broken", ["not json", '{"count": "wrong", "last_at": 0, "history": []}'])
def test_invalid_storage_does_not_trigger_extra_moderation(broken):
    cog, event, channel = fixture()
    cog.bot.db.values[cog._key(100, 42)] = broken
    asyncio.run(cog.on_automod_action(event))
    event.member.timeout.assert_not_awaited()
    event.guild.ban.assert_not_awaited()
    event.member.send.assert_not_awaited()


def test_database_failure_stops_escalation():
    cog, event, channel = fixture()
    cog.bot.db.kv_set = AsyncMock(side_effect=RuntimeError("database unavailable"))
    asyncio.run(cog.on_automod_action(event))
    event.member.timeout.assert_not_awaited()
    event.guild.ban.assert_not_awaited()


def test_missing_member_is_fetched():
    cog, event, channel = fixture()
    event.member = None
    asyncio.run(cog.on_automod_action(event))
    event.guild.fetch_member.assert_awaited_once_with(42)


def test_sqlite_roundtrip_survives_new_cog(tmp_path):
    async def run():
        db = BotDatabase(str(tmp_path / "test.sqlite3"))
        await db.initialize()
        try:
            await db.kv_set(CONFIG_KEY, json.dumps(CONFIG))
            cog, event, channel = fixture(db)
            await cog.on_automod_action(event)
            await db.close()
            await db.initialize()
            assert (await OwnerPingGuardCog(cog.bot)._state(100, 42))["count"] == 1
        finally:
            await db.close()

    asyncio.run(run())


def test_discord_gateway_payload_uses_native_timeout_event():
    cog, event, channel = fixture()
    event.guild.get_member = lambda _: event.member
    state = SimpleNamespace(_get_or_create_unavailable_guild=lambda _: event.guild)
    payload = {
        "action": {"type": 3, "metadata": {"duration_seconds": 1800}},
        "rule_id": "200", "rule_trigger_type": 1, "guild_id": "100", "user_id": "42",
        "channel_id": "500", "matched_keyword": "<@!?1>", "matched_content": "<@1>",
    }
    parsed = discord.AutoModAction(data=payload, state=state)
    asyncio.run(cog.on_automod_action(parsed))
    event.member.send.assert_awaited_once()


def test_log_failure_keeps_saved_history():
    cog, event, channel = fixture()
    channel.send.side_effect = forbidden()

    async def run():
        await cog.on_automod_action(event)
        assert (await cog._state(100, 42))["history"][0]["status"] == "30 minute timeout (AutoMod)"

    asyncio.run(run())


def test_warning_reset_is_logged_and_does_not_clear_sanctions():
    cog, event, channel = fixture()
    event.member.guild_permissions.administrator = True
    ctx = SimpleNamespace(
        guild=event.guild, author=event.member, channel=SimpleNamespace(id=300), reply=AsyncMock(),
    )

    async def run():
        await cog._save(100, 42, {"count": 2, "last_at": time.time(), "history": []})
        await cog.clear_warnings.callback(cog, ctx, event.member)
        state = await cog._state(100, 42)
        assert state["count"] == 0
        assert "reset by 42" in state["history"][0]["status"]
        event.member.timeout.assert_not_awaited()
        event.guild.ban.assert_not_awaited()

    asyncio.run(run())


@pytest.mark.parametrize("public", [False, True])
def test_history_not_disclosed_to_regular_members_or_public_channels(public):
    cog, event, channel = fixture()
    event.member.guild_permissions.administrator = public
    ctx = SimpleNamespace(
        guild=event.guild, author=event.member, channel=SimpleNamespace(id=500 if public else 300), reply=AsyncMock(),
    )
    asyncio.run(cog.ping_warnings.callback(cog, ctx, event.member))
    if public:
        assert ctx.reply.await_args.args[0] == "please use this command in the staff log channel."
    else:
        ctx.reply.assert_not_awaited()


def test_reset_requires_administration_not_only_support_role():
    cog, event, channel = fixture()
    event.member.roles = [SimpleNamespace(id=11)]
    ctx = SimpleNamespace(guild=event.guild, author=event.member, channel=SimpleNamespace(id=300), reply=AsyncMock())
    asyncio.run(cog.clear_warnings.callback(cog, ctx, event.member))
    ctx.reply.assert_not_awaited()


def test_owner_dm_contains_message_author_channel_and_actual_action():
    cog, event, channel = fixture()
    asyncio.run(cog.on_automod_action(event))
    call = cog.bot.owner.send.await_args
    assert call.kwargs["silent"] is True
    assert call.kwargs["allowed_mentions"].users is False
    assert call.kwargs["allowed_mentions"].everyone is False
    embed = call.kwargs["embed"]
    assert "question about coinflip" in embed.description
    assert "kit (42)" == embed.fields[0].value
    assert "#general" in embed.fields[1].value
    assert "https://discord.com/channels/100/500" in embed.fields[1].value
    assert "Timeout de 30 minutos" == embed.fields[2].value
    assert embed.footer.text == "Aviso 1 de 3"


@pytest.mark.parametrize("previous, expected", [(1, "Timeout de 24 horas"), (2, "Ban del Discord")])
def test_owner_is_told_actual_escalated_action(previous, expected):
    cog, event, channel = fixture()

    async def run():
        await cog._save(100, 42, {"count": previous, "last_at": time.time() - 90000, "history": []})
        await cog.on_automod_action(event)
        assert cog.bot.owner.send.await_args.kwargs["embed"].fields[2].value == expected

    asyncio.run(run())


def test_failed_escalation_not_reported_to_owner_as_success():
    cog, event, channel = fixture()
    event.member.timeout.side_effect = forbidden()

    async def run():
        await cog._save(100, 42, {"count": 1, "last_at": time.time() - 90000, "history": []})
        await cog.on_automod_action(event)
        assert "fallo la escalada" in cog.bot.owner.send.await_args.kwargs["embed"].fields[2].value

    asyncio.run(run())


def test_owner_dm_failure_does_not_undo_moderation_or_staff_log():
    cog, event, channel = fixture()
    cog.bot.owner.send.side_effect = forbidden()

    async def run():
        await cog.on_automod_action(event)
        state = await cog._state(100, 42)
        assert state["history"][0]["owner_dm"] == "unavailable"
        assert state["history"][0]["status"] == "30 minute timeout (AutoMod)"
        channel.send.assert_awaited_once()

    asyncio.run(run())


def test_long_text_is_attached_without_loss():
    cog, event, channel = fixture()
    event.content = "*<@1> message*\n" * 400
    captured = []

    async def receive(**kwargs):
        assert len(kwargs["embed"].description) < 4096
        captured.append(kwargs["file"].fp.read().decode("utf-8"))

    cog.bot.owner.send.side_effect = receive
    asyncio.run(cog.on_automod_action(event))
    assert captured == [event.content]


def test_duplicate_event_does_not_send_duplicate_owner_dm():
    cog, event, channel = fixture()

    async def run():
        await cog.on_automod_action(event)
        await cog.on_automod_action(event)

    asyncio.run(run())
    cog.bot.owner.send.assert_awaited_once()


def test_missing_cached_owner_and_missing_content_are_handled():
    cog, event, channel = fixture()
    cog.bot.get_user = lambda _: None
    event.content = ""
    event.guild.get_channel_or_thread = lambda _: None
    asyncio.run(cog.on_automod_action(event))
    cog.bot.fetch_user.assert_awaited_once_with(1)
    assert "Discord no incluyo" in cog.bot.owner.send.await_args.kwargs["embed"].description
