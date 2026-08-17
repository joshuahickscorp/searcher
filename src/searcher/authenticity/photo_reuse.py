"""Screen candidates for photographs they did not take.

The Real gate is fail-closed until something screens the photographs, and until
now nothing did: `IMAGE_THEFT_OR_SCAM` fired only on a flag the production path
never set, so a listing built from the brand's own images published as Real with
no veto. This is the screener that flag was waiting for.

It needs no API and no external corpus. The signal is already in the candidate
set: an image that appears under two different sellers was taken by at most one
of them. A seller reusing their own photograph across their own listings is
ordinary and is not flagged.

Two findings, deliberately kept apart because they mean different things:

- **reused**: the same image appears under more than one seller. One of them is
  not the photographer. This is the shape of a scam listing dressed in the real
  seller's photographs, and of a counterfeit dressed in the brand's.
- **stock**: the same image appears under enough distinct sellers that it is
  catalogue or lookbook imagery rather than anyone's own photograph. A listing
  carrying it is showing the product, not the item for sale.

Neither is proof of dishonesty. A consignment shop legitimately republishes a
brand's photographs. That is exactly why these are inputs to the evidence
model rather than verdicts: the gate decides, this only reports what was seen.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

# An image under this many distinct sellers is catalogue imagery rather than a
# photograph anybody took of the item in hand. Two sellers is reuse; a crowd is
# stock. The line is low because marketplaces re-list aggressively, and the cost
# of calling stock imagery "stock" is only that Real needs other evidence.
STOCK_SELLER_THRESHOLD = 3


def _seller_of(candidate: Any) -> str:
    """Who is offering this listing, as well as the record allows.

    Falls back to the source adapter. Two listings on one marketplace with no
    seller recorded are then treated as one seller, which is the conservative
    direction: it under-reports reuse rather than inventing it.
    """
    meta = getattr(candidate, "seller_metadata", None)
    if isinstance(meta, dict):
        for key in ("seller_id", "seller", "shop", "shop_id", "username", "store"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return f"seller:{value.strip().casefold()}"
    source = getattr(candidate, "source_adapter", None)
    return f"source:{source}" if source else "unknown"


def _families(candidate: Any) -> set[str]:
    """Identity of each image, preferring the strongest key available."""
    out: set[str] = set()
    for image in getattr(candidate, "images", None) or []:
        key = (
            getattr(image, "duplicate_family_id", None)
            or getattr(image, "perceptual_hash", None)
            or getattr(image, "content_digest", None)
        )
        if isinstance(key, str) and key.strip():
            out.add(key.strip())
    return out


def screen_photo_reuse(
    candidates: Sequence[Any] | Iterable[Any],
    *,
    stock_seller_threshold: int = STOCK_SELLER_THRESHOLD,
) -> tuple[set[str], set[str]]:
    """Return (reused_ids, stock_ids) for a candidate set.

    Screening ran once this returns, even when both sets are empty. That is the
    distinction the Real gate depends on: an empty set means nothing was found,
    and `None` means nobody looked.
    """
    rows = list(candidates)
    sellers_by_family: dict[str, set[str]] = defaultdict(set)
    families_by_candidate: dict[str, set[str]] = {}

    for candidate in rows:
        candidate_id = str(getattr(candidate, "candidate_id", "") or "")
        if not candidate_id:
            continue
        families = _families(candidate)
        families_by_candidate[candidate_id] = families
        seller = _seller_of(candidate)
        for family in families:
            sellers_by_family[family].add(seller)

    reused: set[str] = set()
    stock: set[str] = set()
    for candidate_id, families in families_by_candidate.items():
        for family in families:
            count = len(sellers_by_family[family])
            if count >= stock_seller_threshold:
                stock.add(candidate_id)
                reused.add(candidate_id)
            elif count > 1:
                reused.add(candidate_id)
    return reused, stock
