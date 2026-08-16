"""§28.3 top-N escalation bounds. Defaults are starting points, not authored truth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EscalationBounds:
    broad_candidates: int = 500
    normalized_candidates: int = 250
    full_image_download: int = 100
    part_matching: int = 50
    deliberative_review: int = 15
    deep_authenticity: int = 10

    def clip(self, n: int, *, stage: str) -> int:
        limit = {
            "broad": self.broad_candidates,
            "normalized": self.normalized_candidates,
            "download": self.full_image_download,
            "parts": self.part_matching,
            "deliberative": self.deliberative_review,
            "authenticity": self.deep_authenticity,
        }.get(stage, n)
        return max(0, min(n, limit))


DEFAULT_BOUNDS = EscalationBounds()
RECALL_FLOOR = 0.95
KEEP_THRESHOLD = 0.12
