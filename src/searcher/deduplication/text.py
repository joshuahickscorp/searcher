"""Normalized title/description similarity."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[A-Za-z0-9\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]+")


def tokens(text: str) -> set[str]:
    return {part.lower() for part in _TOKEN.findall(text)}


def jaccard(a: str, b: str) -> float:
    left = tokens(a)
    right = tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def text_near_duplicate(a: str, b: str, *, threshold: float = 0.85) -> bool:
    return jaccard(a, b) >= threshold
