"""Create-time text/tag bounds on the API campaign worker."""

from __future__ import annotations

import pytest

from searcher.core.errors import InputError
from searcher.workers.api_campaign import (
    MAX_INTENT_TEXT_CHARS,
    MAX_TAG_CHARS,
    MAX_TAG_COUNT,
    create_api_campaign,
)


def _png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def test_oversize_text_refused(controller: object) -> None:
    with pytest.raises(InputError, match="text exceeds"):
        create_api_campaign(
            controller,  # type: ignore[arg-type]
            uploads=[(_png(), "a.png")],
            text="x" * (MAX_INTENT_TEXT_CHARS + 1),
            tags=["dior"],
            client_search_id=None,
        )


def test_too_many_and_too_long_tags_refused(controller: object) -> None:
    with pytest.raises(InputError, match="at most"):
        create_api_campaign(
            controller,  # type: ignore[arg-type]
            uploads=[(_png(), "a.png")],
            text="ok",
            tags=[f"t{i}" for i in range(MAX_TAG_COUNT + 1)],
            client_search_id=None,
        )
    with pytest.raises(InputError, match="tag exceeds"):
        create_api_campaign(
            controller,  # type: ignore[arg-type]
            uploads=[(_png(), "a.png")],
            text="ok",
            tags=["z" * (MAX_TAG_CHARS + 1)],
            client_search_id=None,
        )


def test_nul_control_and_bidi_refused(controller: object) -> None:
    with pytest.raises(InputError, match="NUL"):
        create_api_campaign(
            controller,  # type: ignore[arg-type]
            uploads=[(_png(), "a.png")],
            text="bad\x00text",
            tags=["dior"],
            client_search_id=None,
        )
    with pytest.raises(InputError, match="control character"):
        create_api_campaign(
            controller,  # type: ignore[arg-type]
            uploads=[(_png(), "a.png")],
            text="ok",
            tags=["di\x01or"],
            client_search_id=None,
        )
    with pytest.raises(InputError, match="bidirectional"):
        create_api_campaign(
            controller,  # type: ignore[arg-type]
            uploads=[(_png(), "a.png")],
            text="ok",
            tags=["di\u202eor"],
            client_search_id=None,
        )


def test_normal_intent_still_creates(controller: object) -> None:
    search_id = create_api_campaign(
        controller,  # type: ignore[arg-type]
        uploads=[(_png(), "a.png")],
        text="Dior Homme General Army Trainer",
        tags=["dior"],
        client_search_id=None,
    )
    assert search_id
    campaign = controller.get(search_id)  # type: ignore[attr-defined]
    assert campaign.search_id == search_id
