"""View classification for listing images."""

from __future__ import annotations

from tests.helpers_matching import make_candidate

from searcher.contracts.enums import ImageRole, ViewHypothesis
from searcher.contracts.models import ListingImage
from searcher.core.ids import sha256_hex
from searcher.matching.pipeline import enrich_candidate
from searcher.matching.synth import REFERENCE_SHOE, render_shoe


def test_roles_and_structure_classify_expected_views() -> None:
    images = [
        ("lateral", render_shoe(REFERENCE_SHOE, view="lateral"), ImageRole.PRODUCT),
        ("heel", render_shoe(REFERENCE_SHOE, view="heel"), ImageRole.PRODUCT),
        ("sole", render_shoe(REFERENCE_SHOE, view="sole"), ImageRole.SOLE),
        ("label", render_shoe(REFERENCE_SHOE, view="label"), ImageRole.LABEL),
    ]
    candidate, pngs = make_candidate(images=images)
    enriched = enrich_candidate(candidate, pngs)
    views = {guess.view for guess in enriched.views}
    assert ViewHypothesis.LATERAL in views
    assert ViewHypothesis.HEEL in views
    assert ViewHypothesis.SOLE in views
    assert ViewHypothesis.LABEL in views


def test_label_role_is_not_overwritten_by_geometry() -> None:
    png = render_shoe(REFERENCE_SHOE, view="label")
    image = ListingImage(
        listing_image_id="lab",
        candidate_id="c",
        remote_url="https://fixture.example/l",
        content_digest=sha256_hex(png),
        role=ImageRole.LABEL,
    )
    candidate, pngs = make_candidate(images=[("lab", png, ImageRole.LABEL)])
    del image
    enriched = enrich_candidate(candidate, pngs)
    assert any(guess.view is ViewHypothesis.LABEL for guess in enriched.views)
