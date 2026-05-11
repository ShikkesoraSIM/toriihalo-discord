from __future__ import annotations

import re


BEATMAP_PATTERNS = [
    re.compile(r"/beatmaps/(\d+)"),
    re.compile(r"/b/(\d+)"),
    re.compile(r"#(?:osu|taiko|fruits|mania)/(\d+)"),
]

SCORE_PATTERNS = [
    re.compile(r"/scores/(\d+)"),
]


def clean_user_identifier(value: str) -> str:
    return value.strip().lstrip("@")


def extract_beatmap_id(value: str) -> int | None:
    value = value.strip()
    if value.isdigit():
        return int(value)
    for pattern in BEATMAP_PATTERNS:
        match = pattern.search(value)
        if match:
            return int(match.group(1))
    return None


def extract_score_id(value: str) -> int | None:
    value = value.strip()
    if value.isdigit():
        return int(value)
    for pattern in SCORE_PATTERNS:
        match = pattern.search(value)
        if match:
            return int(match.group(1))
    return None

