from __future__ import annotations

import re

STOP_WORDS = [
    "帮我规划",
    "帮我安排",
    "帮我们安排",
    "我只想在",
    "我只想",
    "就近吃饭",
    "就近吃吃喝喝",
    "就近吃喝玩乐",
    "吃喝玩乐",
    "吃饭和娱乐",
    "吃饭和玩",
    "吃饭",
    "吃个饭",
    "用餐",
    "聚餐",
    "娱乐",
    "玩耍",
    "玩",
    "逛",
    "安排",
    "规划",
    "推荐",
    "找店",
    "找个",
    "找",
    "附近",
    "周边",
    "旁边",
    "一带",
    "这里",
]

EXPLICIT_PATTERNS = [
    r"(?:我现在在|现在在|我目前在|目前在|人在|我在|在|到|去|位于|住在|从)\s*([一-龥A-Za-z0-9·\-]{2,30})",
    r"([一-龥]{2,20}(?:省|市|区|县|镇|乡|街道|街|路|村|社区|商圈|商场|广场|公园|地铁站|火车站|机场))",
]


def extract_location_hint(text: str) -> str | None:
    source = (text or "").strip()
    if not source:
        return None

    for pattern in EXPLICIT_PATTERNS:
        match = re.search(pattern, source)
        if not match:
            continue
        hint = _cleanup_hint(match.group(1))
        if hint:
            return hint
    return None


def _cleanup_hint(value: str) -> str | None:
    hint = (value or "").strip()
    hint = re.split(r"[，。,.！!？?\n\r]", hint, maxsplit=1)[0].strip()

    for word in sorted(STOP_WORDS, key=len, reverse=True):
        if word in hint:
            hint = hint.split(word, 1)[0].strip()

    for suffix in ["附近的", "附近", "周边", "旁边", "一带", "这里", "这边", "那边"]:
        if hint.endswith(suffix):
            hint = hint[: -len(suffix)].strip()

    hint = hint.strip(" ,，。;；:")
    if len(hint) < 2:
        return None
    return hint
