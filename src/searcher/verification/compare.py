"""Compare recorded listing fields against a structured re-extraction."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urldefrag, urlparse

from searcher.contracts.enums import ExtractionMethod, VerificationVerdict
from searcher.contracts.models import FieldCheck, ListingCandidate, VerificationRecord
from searcher.core.time import UtcDateTime
from searcher.normalization.listing import _availability

CHECKED_FIELDS = ("price", "availability", "title", "seller", "images")


def _as_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _norm_space(value: str) -> str:
    return " ".join(value.split()).casefold()


def _norm_price(value: object | None) -> str | None:
    raw = _as_text(value)
    if raw is None:
        return None
    cleaned = (
        raw.replace(",", "")
        .replace("¥", "")
        .replace("€", "")
        .replace("$", "")
        .replace("£", "")
        .strip()
    )
    for token in ("JPY", "USD", "EUR", "GBP", "CNY"):
        cleaned = cleaned.replace(token, "")
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return _norm_space(raw)
    normalized = format(amount.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def _norm_availability(value: object | None) -> str | None:
    raw = _as_text(value)
    if raw is None:
        return None
    return _availability(raw).value


def _norm_title(value: object | None) -> str | None:
    raw = _as_text(value)
    if raw is None:
        return None
    return _norm_space(raw)


def _norm_seller(value: object | None) -> str | None:
    raw = _as_text(value)
    if raw is None:
        return None
    return _norm_space(raw)


def _image_key(url: str) -> str:
    stripped, _frag = urldefrag(url.strip())
    parsed = urlparse(stripped)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"


def _norm_images(value: object | None) -> str | None:
    if value is None:
        return None
    urls: list[str] = []
    if isinstance(value, str):
        urls = [part for part in value.split("|") if part.strip()]
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                urls.append(item)
            elif isinstance(item, dict):
                remote = item.get("url") or item.get("remote_url")
                if remote:
                    urls.append(str(remote))
    keys = sorted({_image_key(item) for item in urls if item.strip()})
    if not keys:
        return None
    return "|".join(keys)


def recorded_values(candidate: ListingCandidate) -> dict[str, str | None]:
    title = None if candidate.title is None else _as_text(candidate.title.value)
    seller = None
    if candidate.seller_metadata:
        for key in ("name", "seller", "handle", "shop"):
            held = candidate.seller_metadata.get(key)
            if isinstance(held, str) and held.strip():
                seller = held.strip()
                break
    if seller is None and candidate.seller_reported_brand is not None:
        seller = _as_text(candidate.seller_reported_brand.value)
    images = [img.remote_url for img in candidate.images if img.remote_url]
    price = None if candidate.price_original is None else str(candidate.price_original)
    return {
        "price": price,
        "availability": candidate.availability.value,
        "title": title,
        "seller": seller,
        "images": _norm_images(images),
    }


def observed_values(payload: dict[str, Any] | None) -> dict[str, str | None]:
    if not payload:
        return {name: None for name in CHECKED_FIELDS}
    return {
        "price": _as_text(payload.get("price_original") or payload.get("price")),
        "availability": _as_text(payload.get("availability")),
        "title": _as_text(payload.get("title")),
        "seller": _as_text(payload.get("seller") or payload.get("brand")),
        "images": _norm_images(payload.get("images")),
    }


_NORMALIZERS = {
    "price": _norm_price,
    "availability": _norm_availability,
    "title": _norm_title,
    "seller": _norm_seller,
    "images": _norm_images,
}


def _images_agree(recorded: str | None, observed: str | None) -> bool:
    if not recorded or not observed:
        return False
    rec = set(recorded.split("|"))
    obs = set(observed.split("|"))
    return bool(rec & obs)


def compare_fields(
    candidate: ListingCandidate,
    payload: dict[str, Any] | None,
    *,
    checked_at: UtcDateTime,
    extraction_method: ExtractionMethod | None,
    fetch_note: str | None = None,
) -> list[FieldCheck]:
    recorded = recorded_values(candidate)
    observed = observed_values(payload)
    checks: list[FieldCheck] = []
    for field in CHECKED_FIELDS:
        rec_raw = recorded[field]
        obs_raw = observed[field]
        rec_n = _NORMALIZERS[field](rec_raw)
        obs_n = _NORMALIZERS[field](obs_raw)
        if obs_n is None:
            reason = fetch_note or "field not present in structured data on the listing page"
            verdict = VerificationVerdict.ABSENT
        elif rec_n is None:
            reason = "no earlier value recorded to compare"
            verdict = VerificationVerdict.ABSENT
        elif field == "images" and _images_agree(rec_n, obs_n):
            reason = "image set overlaps the listing page"
            verdict = VerificationVerdict.AGREES
        elif rec_n == obs_n:
            reason = "recorded value matches the listing page"
            verdict = VerificationVerdict.AGREES
        else:
            reason = f"{field} changed: recorded {rec_raw}, observed {obs_raw}"
            verdict = VerificationVerdict.DISAGREES
        checks.append(
            FieldCheck(
                field=field,
                recorded=rec_raw,
                observed=obs_raw,
                verdict=verdict,
                reason=reason,
                checked_at=checked_at,
                extraction_method=extraction_method,
            )
        )
    return checks


def statements_for(
    record: VerificationRecord,
) -> tuple[list[str], list[str], list[str]]:
    support: list[str] = []
    contradictions: list[str] = []
    missing: list[str] = []
    for item in record.fields:
        line = f"{item.field}: {item.reason}"
        if item.verdict is VerificationVerdict.AGREES:
            support.append(line)
        elif item.verdict is VerificationVerdict.DISAGREES:
            contradictions.append(line)
        else:
            missing.append(line)
    return support, contradictions, missing
