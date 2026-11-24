import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bot.preview_stats import PreviewSettings, StatsPreviewBot


def test_preview_never_falls_back_to_production_token(monkeypatch):
    monkeypatch.delenv("DISCORD_PREVIEW_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_PREVIEW_GUILD_ID", raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "production-must-not-be-used")
    monkeypatch.setenv("DISCORD_GUILD_ID", "999")
    with pytest.raises(ValidationError):
        PreviewSettings(_env_file=None)


def test_preview_only_loads_stats_and_syncs_test_guild():
    async def run():
        settings = PreviewSettings(_env_file=None, DISCORD_PREVIEW_TOKEN="test", DISCORD_PREVIEW_GUILD_ID=123)
        bot = StatsPreviewBot(settings)
        bot.db.initialize = AsyncMock()
        bot.db.close = AsyncMock()
        bot.tree.sync = AsyncMock(return_value=[])
        try:
            async with bot:
                await bot.setup_hook()
                assert list(bot.cogs) == ["OsuStatsCog"]
                assert bot.db._db_path.name == "halo-preview.sqlite3"
                assert bot.tree.sync.await_count == 1
                assert bot.tree.sync.call_args.kwargs["guild"].id == 123
                assert not bot.intents.members and not bot.intents.message_content
                assert bot.get_command("rs") is not None
        finally:
            await bot.close()
    asyncio.run(run())

