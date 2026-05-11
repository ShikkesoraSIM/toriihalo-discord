from bot.utils.formatting import accuracy_to_percent, format_accuracy, format_mods, format_pp


def test_accuracy_normalization() -> None:
    assert round(accuracy_to_percent(0.9876), 2) == 98.76
    assert round(accuracy_to_percent(98.76), 2) == 98.76


def test_format_accuracy() -> None:
    assert format_accuracy(0.995) == "99.50%"


def test_format_mods() -> None:
    assert format_mods([]) == "NM"
    assert format_mods([{"acronym": "HD"}, {"acronym": "DT"}]) == "HDDT"


def test_format_pp() -> None:
    assert format_pp(123.456) == "123.46pp"

