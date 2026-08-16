"""Listing-page verification: structured extract, field verdicts, price change."""

from __future__ import annotations

from decimal import Decimal

from searcher.contracts.enums import (
    Availability,
    BucketInternal,
    BucketPublic,
    ExtractionMethod,
    FactClass,
    FactOrigin,
    SourceAdmission,
    VerificationVerdict,
)
from searcher.contracts.models import (
    BucketDecision,
    BucketDecisionFields,
    ListingCandidate,
    ListingImage,
)
from searcher.contracts.primitives import PublicExplanation, classified
from searcher.core.time import parse_utc
from searcher.verification.compare import compare_fields
from searcher.verification.extract import extract_rdfa, extract_structured
from searcher.verification.runner import apply_record, merge_verification

_TS = parse_utc("2007-06-15T12:00:00+00:00")

JSON_LD = """
<html><head>
<script type="application/ld+json">
{"@type":"Product","name":"Army Trainer","brand":{"name":"Dior Homme"},
 "offers":{"price":"48000","priceCurrency":"JPY","availability":"https://schema.org/InStock"},
 "image":"https://shop.example/img.jpg"}
</script>
</head><body><h1>visible</h1></body></html>
"""

MICRODATA = """
<html><body>
<div itemscope itemtype="https://schema.org/Product">
  <h1 itemprop="name">Micro Trainer</h1>
  <span itemprop="brand">Dior Homme</span>
  <span itemprop="price">120</span>
  <meta itemprop="priceCurrency" content="EUR">
  <link itemprop="availability" href="https://schema.org/InStock">
  <img itemprop="image" src="https://shop.example/m.jpg">
</div>
</body></html>
"""

RDFA = """
<html><body>
<div typeof="schema:Product">
  <h1 property="name">RDFa Trainer</h1>
  <span property="brand">Dior Homme</span>
  <span property="price">99</span>
  <meta property="priceCurrency" content="USD">
  <img property="image" src="https://shop.example/r.jpg">
</div>
</body></html>
"""

EMPTY = "<html><body><p>nothing structured here</p></body></html>"


def _candidate(
    *,
    price: str = "48000",
    title: str = "Army Trainer",
    seller: str = "Dior Homme",
    availability: Availability = Availability.LIVE,
    image: str = "https://shop.example/img.jpg",
) -> ListingCandidate:
    return ListingCandidate(
        candidate_id="cand-1",
        canonical_url="https://shop.example/products/gat",
        source_adapter="rebag",
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        seller_reported_brand=classified(seller, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        price_original=Decimal(price),
        currency_original="JPY",
        availability=availability,
        seller_metadata={"name": seller},
        images=[
            ListingImage(
                listing_image_id="img-1",
                candidate_id="cand-1",
                remote_url=image,
            )
        ],
        first_seen_at=_TS,
        last_checked_at=_TS,
        explanation=PublicExplanation(live_status=availability, last_checked_at=_TS),
    )


def test_json_ld_product_is_preferred() -> None:
    payload = extract_structured(JSON_LD, "https://shop.example/products/gat")
    assert payload is not None
    assert payload["title"] == "Army Trainer"
    assert payload["price_original"] == "48000"
    assert payload["extraction_method"] == ExtractionMethod.JSON_LD.value


def test_microdata_is_used_when_json_ld_absent() -> None:
    payload = extract_structured(MICRODATA, "https://shop.example/products/m")
    assert payload is not None
    assert payload["title"] == "Micro Trainer"
    assert payload["extraction_method"] == ExtractionMethod.MICRODATA.value


def test_rdfa_is_used_when_higher_methods_absent() -> None:
    payload = extract_rdfa(RDFA, "https://shop.example/products/r")
    assert payload is not None
    assert payload["title"] == "RDFa Trainer"
    payload = extract_structured(RDFA, "https://shop.example/products/r")
    assert payload is not None
    assert payload["extraction_method"] == ExtractionMethod.RDFA.value


def test_absent_when_no_structured_data() -> None:
    assert extract_structured(EMPTY, "https://shop.example/x") is None
    checks = compare_fields(
        _candidate(),
        None,
        checked_at=_TS,
        extraction_method=None,
        fetch_note="field not present in structured data on the listing page",
    )
    assert {item.field for item in checks} == {
        "price",
        "availability",
        "title",
        "seller",
        "images",
    }
    assert all(item.verdict is VerificationVerdict.ABSENT for item in checks)


def test_price_change_is_disagreement_and_candidate_is_kept() -> None:
    candidate = _candidate(price="48000")
    payload = {
        "title": "Army Trainer",
        "seller": "Dior Homme",
        "price_original": "52000",
        "availability": "https://schema.org/InStock",
        "images": ["https://shop.example/img.jpg"],
        "extraction_method": "json_ld",
    }
    checks = compare_fields(
        candidate,
        payload,
        checked_at=_TS,
        extraction_method=ExtractionMethod.JSON_LD,
    )
    by_field = {item.field: item for item in checks}
    assert by_field["price"].verdict is VerificationVerdict.DISAGREES
    assert "52000" in by_field["price"].reason
    assert by_field["title"].verdict is VerificationVerdict.AGREES
    assert by_field["seller"].verdict is VerificationVerdict.AGREES
    assert by_field["availability"].verdict is VerificationVerdict.AGREES
    from searcher.contracts.models import VerificationRecord

    record = VerificationRecord(
        candidate_id=candidate.candidate_id,
        url=candidate.canonical_url,
        checked_at=_TS,
        fields=checks,
        extraction_method=ExtractionMethod.JSON_LD,
    )
    updated = apply_record(candidate, record)
    assert updated.canonical_url == candidate.canonical_url
    assert updated.price_original == Decimal("48000")
    assert updated.verification is not None
    assert any("price changed" in line for line in updated.explanation.contradictions)
    decision = BucketDecision(
        candidate_id=candidate.candidate_id,
        decision=BucketDecisionFields(
            internal=BucketInternal.REAL, public=BucketPublic.REAL
        ),
        policy_version="matching-1",
        item_match_lower_bound=0.8,
        authenticity_lower_bound=0.8,
        evidence_completeness=0.5,
        explanation=PublicExplanation(live_status=Availability.LIVE),
    )
    merged = merge_verification(decision, updated)
    assert merged.decision.public is BucketPublic.REAL
    assert any("price changed" in line for line in merged.explanation.contradictions)


def test_verify_candidate_records_agrees_and_absent() -> None:
    """A permitted-source candidate keeps a verification record with mixed verdicts."""
    import os
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from searcher.sources.admission import AdmissionGate
    from searcher.sources.fetch_modes import Escalator
    from searcher.sources.http import HonestHttpClient
    from searcher.sources.manifest import build_manifest
    from searcher.sources.robots import RobotsCache
    from searcher.verification.runner import verify_candidate

    html = b"""<!doctype html><html><head>
<script type="application/ld+json">
{"@type":"Product","name":"Army Trainer",
 "offers":{"price":"52000","priceCurrency":"JPY",
           "availability":"https://schema.org/InStock"}}
</script></head><body><h1>Army Trainer</h1></body></html>"""
    robots = b"User-agent: *\nAllow: /\n"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            body = robots if path == "/robots.txt" else html
            ctype = "text/plain" if path == "/robots.txt" else "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    os.environ["SEARCHER_ALLOW_LOOPBACK"] = "1"
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    url = f"http://{host}:{port}/products/gat"
    candidate = _candidate()
    candidate = candidate.model_copy(update={"canonical_url": url})
    http = HonestHttpClient()
    escalator = Escalator(http, AdmissionGate(RobotsCache(), http), cache=None)
    manifest = build_manifest(
        source_id="rebag",
        adapter="rebag",
        domain="127.0.0.1",
        access_method="http_get",
        admission_status=SourceAdmission.ADMITTED,
        allowed_use="fixture re-check of an admitted source",
    )
    try:
        updated = verify_candidate(
            candidate, manifest, escalator, search_id="search-verify"
        )
    finally:
        http.close()
        httpd.shutdown()
        thread.join(timeout=2)
    assert updated.verification is not None
    by_field = {item.field: item for item in updated.verification.fields}
    assert by_field["title"].verdict is VerificationVerdict.AGREES
    assert by_field["price"].verdict is VerificationVerdict.DISAGREES
    assert by_field["seller"].verdict is VerificationVerdict.ABSENT
    assert updated.price_original == Decimal("48000")
    assert updated.verification.checked_at is not None
