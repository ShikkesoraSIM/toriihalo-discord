import asyncio
import json
from unittest.mock import AsyncMock

from bot.torii_api import ToriiApiClient


def test_full_mod_settings_sent_to_server():
    async def run():
        api = ToriiApiClient("https://example.com", "https://example.com")
        api._request = AsyncMock(return_value={"star_rating": 8.65})
        mods = [{"acronym": "DT", "settings": {"speed_change": 1.85}},
                {"acronym": "DA", "settings": {"circle_size": 9}}]
        try:
            assert await api.get_beatmap_attributes(50, mods, "osurx") == {"star_rating": 8.65}
            call = api._request.call_args
            assert call.args == ("POST", "/api/v2/beatmaps/50/attributes")
            assert call.kwargs["params"][0] == ("ruleset", "osurx")
            assert [json.loads(value) for key, value in call.kwargs["params"] if key == "mods"] == mods
        finally:
            await api.close()
    asyncio.run(run())
