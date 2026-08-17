"""§20.4 hard vetoes. A hard veto bars both public tabs."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from searcher.contracts.enums import Availability
from searcher.contracts.models import ListingCandidate
from searcher.retrieval.text import self_declared_replica

WRONG_PRODUCT = "WRONG_PRODUCT"
HARD_COLOURWAY = "HARD_COLOURWAY"
SELF_DECLARED_REPLICA = "SELF_DECLARED_REPLICA"
STRONG_COUNTERFEIT = "STRONG_COUNTERFEIT_EVIDENCE"
IMAGE_THEFT_OR_SCAM = "IMAGE_THEFT_OR_SCAM"
MALICIOUS_URL = "MALICIOUS_URL"
INACCESSIBLE = "INACCESSIBLE_DESTINATION"
DEAD_LISTING = "DEAD_LISTING"
DUPLICATE_NO_UTILITY = "DUPLICATE_NO_UTILITY"
INSUFFICIENT_MATCH = "INSUFFICIENT_MATCH"
POLICY_REFUSAL = "POLICY_REFUSAL"

_PRIVATE = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
)


def url_is_malicious(url: str) -> bool:
    raw = (url or "").strip()
    if not raw:
        return True
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme in {"javascript", "data", "file", "about"}:
        return True
    if scheme and scheme not in {"http", "https"}:
        return True
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "metadata.google.internal"}:
        return True
    if host.endswith(".internal") or host.endswith(".localhost"):
        return True
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _PRIVATE)
    except ValueError:
        return False


_ITEM_HARD = re.compile(
    r"eyelet-count-mismatch|panel-count-mismatch|outsole-geometry-mismatch|"
    r"wrong-product|wrong-last|wrong-model"
)
_FOOTWEAR_ITEM_HARD = re.compile(
    r"eyelet-count-mismatch|panel-count-mismatch|outsole-geometry-mismatch|wrong-last"
)
_AUTH_HARD = re.compile(
    r"construction-|label-code-incompatible|logo-incompatible|"
    r"self-declared-replica|image-theft|strong-counterfeit"
)


def collect_hard_vetoes(
    *,
    candidate: ListingCandidate,
    item_hard: list[str],
    auth_hard: list[str],
    item_lower: float,
    destination_verified: bool,
    destination_attested: bool = False,
    stolen_photo: bool,
    duplicate_no_utility: bool,
    dead_listing_is_hard_veto: bool,
    plausible_floor: float,
    exact_colour_required: bool,
    apply_footwear_item_rules: bool = True,
) -> list[str]:
    vetoes: list[str] = []
    if url_is_malicious(candidate.canonical_url):
        vetoes.append(MALICIOUS_URL)
    text = " ".join(
        str(part.value) for part in (candidate.title, candidate.description) if part and part.value
    )
    if self_declared_replica(text):
        vetoes.append(SELF_DECLARED_REPLICA)
    item_codes = list(item_hard)
    if not apply_footwear_item_rules:
        item_codes = [code for code in item_codes if not _FOOTWEAR_ITEM_HARD.search(code)]
    if any(_ITEM_HARD.search(code) for code in item_codes):
        vetoes.append(WRONG_PRODUCT)
    if exact_colour_required and any("colourway" in code for code in item_hard + auth_hard):
        vetoes.append(HARD_COLOURWAY)
    if "self-declared-replica" in auth_hard and SELF_DECLARED_REPLICA not in vetoes:
        vetoes.append(SELF_DECLARED_REPLICA)
    auth_counterfeit = [
        code
        for code in auth_hard
        if "label-code-incompatible" in code or "logo-incompatible" in code
    ]
    if auth_counterfeit and WRONG_PRODUCT not in vetoes:
        # Same overall model, but marks/labels contradict the authenticity reference.
        vetoes.append(STRONG_COUNTERFEIT)
    if stolen_photo or any("image-theft" in code for code in auth_hard):
        vetoes.append(IMAGE_THEFT_OR_SCAM)
    if (
        not destination_verified
        and not destination_attested
        and candidate.availability is Availability.UNKNOWN
    ):
        # Inaccessible means we have no reason to believe this URL resolves.
        # A URL the shop itself published in its own product feed is not that:
        # our own fetch being refused - a challenge, a rate limit - says
        # something about us, not about whether the listing exists. Attested is
        # weaker than verified and never claims the listing is live; it only
        # stops a refused fetch from reading as a dead destination.
        vetoes.append(INACCESSIBLE)
    if dead_listing_is_hard_veto and candidate.availability not in {
        Availability.LIVE,
        Availability.UNKNOWN,
    }:
        vetoes.append(DEAD_LISTING)
    if duplicate_no_utility:
        vetoes.append(DUPLICATE_NO_UTILITY)
    if item_lower < plausible_floor and WRONG_PRODUCT not in vetoes:
        vetoes.append(INSUFFICIENT_MATCH)
    return list(dict.fromkeys(vetoes))
