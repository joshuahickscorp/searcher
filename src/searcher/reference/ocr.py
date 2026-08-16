"""§11.7 OCR. Every extraction is EXTRACTED and bound to a region + confidence."""

from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
from pathlib import Path

from searcher.contracts.enums import FactClass, FactOrigin
from searcher.contracts.models import TextObservation
from searcher.reference.injection import looks_like_instruction
from searcher.reference.vocab import COLOURS, MATERIALS, SIZE_HINTS

_SIZE_RE = re.compile(
    r"^(?:size|eu|us|uk|t\.?|taille)?\s*([3-5]\d(?:\.\d)?|[6-9]|1[0-6]|2[2-9](?:\.\d)?)$",
    re.I,
)
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
_SEASON_RE = re.compile(r"^(?:ss|aw|fw|resort|pre-?fall|cruise)\s*'?\d{2}$", re.I)
_COUNTRY_RE = re.compile(r"^(made\s+in|fabriqu[eé]\s+en|hergestellt\s+in)\b", re.I)
_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{4,}$")
_HANDLE_RE = re.compile(r"^@[\w.]{2,}$")
_PRICE_RE = re.compile(r"^[$€£¥₩]\s?\d|\d+\s?(usd|eur|gbp|jpy|krw)$", re.I)
_NOT_BRAND = frozenset(
    {
        "made",
        "size",
        "the",
        "and",
        "for",
        "new",
        "sold",
        "from",
        "with",
        "this",
        "that",
        "italy",
        "france",
        "spain",
        "china",
    }
)


def classify_ocr_token(text: str) -> str:
    raw = text.strip()
    lower = raw.lower()
    if looks_like_instruction(raw):
        return "instruction"
    if _HANDLE_RE.match(raw):
        return "handle"
    if _PRICE_RE.search(lower) or lower in {"sold", "like", "likes", "save"}:
        return "overlay"
    if _COUNTRY_RE.search(lower) or lower in {"italy", "france", "spain", "portugal", "china"}:
        return "country"
    if lower in MATERIALS:
        return "material"
    if lower in COLOURS:
        return "colour"
    if _SEASON_RE.match(lower):
        return "season"
    if _YEAR_RE.match(raw):
        return "season"
    if lower in SIZE_HINTS or _SIZE_RE.match(lower.replace(" ", "")):
        return "size"
    if _CODE_RE.match(raw) and any(ch.isdigit() for ch in raw) and any(ch.isalpha() for ch in raw):
        return "product_code"
    if raw.isupper() and 4 <= len(raw) <= 16 and raw.isalpha() and lower not in _NOT_BRAND:
        return "brand"
    return "unknown"


def _observations_from_tsv(
    tsv: str, scale_x: float = 1.0, scale_y: float = 1.0
) -> list[TextObservation]:
    observations: list[TextObservation] = []
    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t")
    for row in reader:
        text = str(row.get("text") or "").strip()
        try:
            confidence = float(row.get("conf") or -1)
        except ValueError:
            confidence = -1
        if not text or confidence < 0:
            continue
        kind = classify_ocr_token(text)
        observations.append(
            TextObservation(
                text=text,
                region=(
                    float(row.get("left") or 0) * scale_x,
                    float(row.get("top") or 0) * scale_y,
                    float(row.get("width") or 0) * scale_x,
                    float(row.get("height") or 0) * scale_y,
                ),
                confidence=max(0.0, min(1.0, confidence / 100.0)),
                fact_class=FactClass.EXTRACTED,
                origin=FactOrigin.EXTRACTOR,
                kind=kind,
                injection_candidate=kind == "instruction",
            )
        )
    return observations


def run_tesseract(path: Path, *, timeout: float = 20.0) -> list[TextObservation]:
    executable = shutil.which("tesseract")
    if executable is None:
        return []
    try:
        result = subprocess.run(
            [executable, str(path), "stdout", "--psm", "11", "tsv"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0 or not result.stdout:
        return []
    return flag_instruction_spans(_observations_from_tsv(result.stdout))


def flag_instruction_spans(observations: list[TextObservation]) -> list[TextObservation]:
    """Mark tokens that participate in an instruction-like phrase.

    Tesseract emits one token per word. The policy still applies to the
    reconstructed line, not only to a single token that happens to match.
    """
    if not observations:
        return observations
    joined = " ".join(item.text for item in observations)
    if not looks_like_instruction(joined):
        return observations
    flagged: list[TextObservation] = []
    for item in observations:
        flagged.append(
            item.model_copy(
                update={
                    "kind": "instruction" if item.kind == "unknown" else item.kind,
                    "injection_candidate": True,
                    "fact_class": FactClass.EXTRACTED,
                }
            )
        )
    return flagged


def merge_nearby(observations: list[TextObservation]) -> list[TextObservation]:
    """Keep tokens separate. Line grouping is a later nicety, not identity."""
    return flag_instruction_spans(observations)
