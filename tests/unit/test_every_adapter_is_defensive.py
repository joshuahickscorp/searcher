"""Every adapter, against the inputs the open web actually returns.

The source layer sits below the §32.1 branch floor and the gap concentrates in
the adapters - 231 uncovered statements spread across files that all implement
one protocol. Writing a suite per adapter would cover them one at a time and
would keep missing the same class of branch. This parametrises the registry
instead, so a new adapter inherits the contract the moment it is registered.

The contract under test is defensiveness. A remote page is not a fixture: it
arrives empty, truncated, in the wrong content type, as an error page dressed
as HTTP 200, or as bytes that are not text at all. An adapter that raises on any
of those takes the campaign down with it, and the coverage map showed those
paths were never exercised.
"""

from __future__ import annotations

import pytest

from searcher.contracts.enums import SourceOutcome
from searcher.sources.adapters import ADAPTER_REGISTRY
from searcher.sources.fetch_modes import FetchedDocument, FetchResult

ADAPTER_IDS = sorted(ADAPTER_REGISTRY)

HOSTILE_BODIES = [
    pytest.param(b"", id="empty"),
    pytest.param(b"   \n\t  ", id="whitespace"),
    pytest.param(b"<html>", id="truncated-html"),
    pytest.param(b"<html><body><div class=", id="cut-mid-attribute"),
    pytest.param(b"not json, not html, just words", id="prose"),
    pytest.param(b"{", id="truncated-json"),
    pytest.param(b'{"products": null}', id="json-null-field"),
    pytest.param(b'{"products": [{}]}', id="json-empty-product"),
    pytest.param(b"\x00\x01\x02\xff\xfe", id="binary"),
    pytest.param("<html><p>café — ¥100</p></html>".encode(), id="utf8-punctuation"),
    pytest.param(b"<html><body>" + b"<div>" * 500 + b"</body></html>", id="deeply-nested"),
]


def _doc(body: bytes, url: str = "https://example.test/item/1") -> FetchedDocument:
    result = FetchResult(
        attempt_id="probe",
        url=url,
        outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
        http_status=200,
        canonical_url=url,
        content_type="text/html",
    )
    return FetchedDocument(result=result, body=body, headers={}, final_url=url)


@pytest.mark.parametrize("adapter_id", ADAPTER_IDS)
def test_manifest_is_answerable_without_network(adapter_id: str) -> None:
    """A manifest describes the adapter itself and must never need a fetch."""
    manifest = ADAPTER_REGISTRY[adapter_id]().manifest()
    assert manifest is not None
    assert getattr(manifest, "source_id", None) or getattr(manifest, "name", None)


@pytest.mark.parametrize("adapter_id", ADAPTER_IDS)
@pytest.mark.parametrize("body", HOSTILE_BODIES)
def test_parse_never_raises_on_a_hostile_body(adapter_id: str, body: bytes) -> None:
    adapter = ADAPTER_REGISTRY[adapter_id]()
    parse = getattr(adapter, "parse", None)
    if not callable(parse):
        pytest.skip(f"{adapter_id} does not parse documents")
    try:
        listings = parse(_doc(body))
    except Exception as exc:  # noqa: BLE001 - the point of the test
        pytest.fail(f"{adapter_id} raised {type(exc).__name__} on a hostile body: {exc}")
    assert listings is None or isinstance(listings, list), (
        f"{adapter_id} returned {type(listings).__name__}; a parse yields listings or nothing"
    )


def test_a_soft_error_page_is_not_classified_as_a_product() -> None:
    """The commonest real failure: a 404 body served with a 200 status line.

    This belongs to the classifier, not to each adapter. URL shape otherwise
    wins over a misleading body, which is right for a real listing and wrong
    here - the URL still looks like a product URL, so the error page was
    classified PRODUCT and every adapter below manufactured a listing from it.
    Measured before the fix: 28 of 31 adapters produced one.
    """
    from searcher.contracts.enums import DocumentClass
    from searcher.sources.classify import classify_acquired_document

    url = "https://example.test/products/gone"
    for body in (
        b"<html><head><title>404 Not Found</title></head><body>Page not found</body></html>",
        b"<html><head><title>Page Not Found</title></head><body>Sorry</body></html>",
        b"<html><head><title>410 Gone</title></head><body>No longer available</body></html>",
    ):
        assert classify_acquired_document(url=url, body=body) is DocumentClass.OTHER, body[:40]


def test_a_real_product_page_is_still_a_product() -> None:
    """The guard must not swallow listings that merely mention the words."""
    from searcher.contracts.enums import DocumentClass
    from searcher.sources.classify import classify_acquired_document

    body = (
        b"<html><head><title>Archive Alpha Trainer 2007</title></head><body>"
        b"<h1>Archive Alpha Trainer</h1><p>Price 100</p>"
        b"<p>If your size is not found, contact us.</p>"
        + b"<p>detail</p>" * 200
        + b"</body></html>"
    )
    assert (
        classify_acquired_document(url="https://example.test/products/alpha", body=body)
        is DocumentClass.PRODUCT
    )
