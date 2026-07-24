from __future__ import annotations

from typing import Any


MODE_DISPLAY = {
    "osu": "osu!",
    "taiko": "osu!taiko",
    "fruits": "osu!catch",
    "mania": "osu!mania",
    "osurx": "osu!relax",
    "osuap": "osu!autopilot",
    "taikorx": "taiko relax",
    "fruitsrx": "catch relax",
}


def mode_display_name(mode: str | None) -> str:
    if not mode:
        return "unknown"
    return MODE_DISPLAY.get(mode.lower(), mode)


def format_number(value: int | float | None) -> str:
    if value is None:
        return "0"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{value:,}"


def format_pp(value: int | float | None) -> str:
    if value is None:
        return "0pp"
    return f"{float(value):,.2f}pp"


def accuracy_to_percent(value: float | int | None) -> float:
    if value is None:
        return 0.0
    acc = float(value)
    if acc <= 1.0:
        acc *= 100.0
    return acc


def format_accuracy(value: float | int | None) -> str:
    return f"{accuracy_to_percent(value):.2f}%"


RATE_MODS = {"DT", "NC", "HT", "DC"}

# Difficulty Adjust: los stats que la persona puede overridear. Solo mostramos los
# presentes; extended_limits se ignora a proposito porque es meta (deja pasar valores
# fuera de rango), no un numero visible de por si. scroll_speed va aparte (taiko/mania).
DA_STAT_SETTINGS = (
    ("circle_size", "CS"),
    ("approach_rate", "AR"),
    ("overall_difficulty", "OD"),
    ("drain_rate", "HP"),
)


def _trim_number(value: float) -> str:
    """5.0 -> '5', 9.50 -> '9.5', 1.30 -> '1.3' (sin ceros ni punto de sobra)."""
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_difficulty_adjust(acronym: str, settings: dict) -> str:
    """DA (CS5, AR9.5, OD8) — solo los stats que la persona toco. Sin overrides: 'DA'."""
    parts: list[str] = []
    for key, label in DA_STAT_SETTINGS:
        value = settings.get(key)
        if value is not None:
            parts.append(f"{label}{_trim_number(float(value))}")
    scroll = settings.get("scroll_speed")
    if scroll is not None:
        parts.append(f"{_trim_number(float(scroll))}x scroll")
    if parts:
        return f"{acronym} ({', '.join(parts)})"
    return acronym


def format_mods(mods: Any) -> str:
    if not mods:
        return "NM"
    if isinstance(mods, str):
        return mods
    if isinstance(mods, list):
        result: list[str] = []
        for mod in mods:
            if isinstance(mod, dict):
                acronym = mod.get("acronym")
                if not acronym:
                    continue
                settings = mod.get("settings") or {}
                if acronym in RATE_MODS:
                    speed = settings.get("speed_change")
                    if speed is not None:
                        result.append(f"{acronym} {_trim_number(float(speed))}x")
                    else:
                        result.append(acronym)
                elif acronym == "DA":
                    result.append(_format_difficulty_adjust(acronym, settings))
                else:
                    result.append(str(acronym))
            elif isinstance(mod, str):
                result.append(mod)
        return "".join(result) if result else "NM"
    return "NM"


def truncate(text: str, max_len: int = 1024) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
