from bot.utils.parsing import extract_beatmap_id, extract_score_id


def test_extract_beatmap_id_from_numeric() -> None:
    assert extract_beatmap_id("12345") == 12345


def test_extract_beatmap_id_from_url() -> None:
    assert extract_beatmap_id("https://lazer.shikkesora.com/beatmapsets/123#osu/456") == 456
    assert extract_beatmap_id("https://osu.ppy.sh/beatmaps/98765") == 98765
    assert extract_beatmap_id("https://osu.ppy.sh/b/777") == 777


def test_extract_score_id_from_url() -> None:
    assert extract_score_id("https://lazer.shikkesora.com/scores/4321") == 4321
    assert extract_score_id("4321") == 4321

