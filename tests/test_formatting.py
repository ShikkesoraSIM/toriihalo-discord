from bot.utils.formatting import accuracy_to_percent, format_accuracy, format_mods, format_pp


def test_accuracy_normalization() -> None:
    assert round(accuracy_to_percent(0.9876), 2) == 98.76
    assert round(accuracy_to_percent(98.76), 2) == 98.76


def test_format_accuracy() -> None:
    assert format_accuracy(0.995) == "99.50%"


def test_format_mods() -> None:
    assert format_mods([]) == "NM"
    assert format_mods([{"acronym": "HD"}, {"acronym": "DT"}]) == "HDDT"


def test_format_mods_rate() -> None:
    # el rate change de DT/NC/HT/DC (lo de Remi) sigue intacto tras el refactor
    assert format_mods([{"acronym": "DT"}]) == "DT"
    assert format_mods([{"acronym": "DT", "settings": {"speed_change": 1.3}}]) == "DT 1.3x"
    assert format_mods([{"acronym": "DT", "settings": {"speed_change": 2.0}}]) == "DT 2x"
    assert format_mods([{"acronym": "HT", "settings": {"speed_change": 0.75}}]) == "HT 0.75x"


def test_format_mods_difficulty_adjust() -> None:
    assert format_mods([{"acronym": "DA", "settings": {}}]) == "DA"
    assert format_mods([{"acronym": "DA", "settings": {"circle_size": 5}}]) == "DA (CS5)"
    assert (
        format_mods([{"acronym": "DA", "settings": {"circle_size": 5, "approach_rate": 9.5, "overall_difficulty": 8}}])
        == "DA (CS5, AR9.5, OD8)"
    )
    # HP y orden estable CS/AR/OD/HP
    assert (
        format_mods([{"acronym": "DA", "settings": {"drain_rate": 6, "circle_size": 4, "overall_difficulty": 9.2, "approach_rate": 10.3}}])
        == "DA (CS4, AR10.3, OD9.2, HP6)"
    )
    # extended_limits no se muestra de por si; scroll_speed de taiko/mania sí
    assert format_mods([{"acronym": "DA", "settings": {"approach_rate": 11, "extended_limits": True}}]) == "DA (AR11)"
    assert format_mods([{"acronym": "DA", "settings": {"scroll_speed": 1.5, "overall_difficulty": 7}}]) == "DA (OD7, 1.5x scroll)"
    # combinado con otros mods
    assert format_mods([{"acronym": "HD"}, {"acronym": "DA", "settings": {"circle_size": 4, "approach_rate": 9}}]) == "HDDA (CS4, AR9)"


def test_format_pp() -> None:
    assert format_pp(123.456) == "123.46pp"

