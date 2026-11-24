import asyncio

from bot.config import Settings
from bot.main import ToriiBot


def test_production_bot_receives_emoji_updates():
    async def run():
        bot = ToriiBot(Settings(_env_file=None, DISCORD_TOKEN="test"))
        try:
            assert bot.intents.emojis_and_stickers
        finally:
            await bot.close()
    asyncio.run(run())
