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
                if acronym:
                    result.append(str(acronym))
            elif isinstance(mod, str):
                result.append(mod)
        return "".join(result) if result else "NM"
    return "NM"


def truncate(text: str, max_len: int = 1024) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"

