"""A size is fit information, never part of a brand.

Observed live: "PRADA(プラダ) ハイヒールパンプス ブラック サイズ 38 1/2" produced the
brand "PRADA 38", so the campaign asked shop.kind.co.jp for its "prada-38" and
"38" collections. Both answered HTTP 200 with an empty product list, which read
as a source searched with no match, while the real "prada" collection holds 250
products. The search reported COMPLETE having found nothing.
"""

from __future__ import annotations

from searcher.hypotheses.item import parse_user_text


def test_size_after_a_marker_is_not_a_brand_token() -> None:
    parsed = parse_user_text("PRADA(プラダ) ハイヒールパンプス ブラック サイズ 38 1/2", ["PRADA"])
    assert parsed.brand_tokens == ["PRADA"]
    assert "38" not in parsed.brand_tokens


def test_a_bare_number_never_becomes_the_second_half_of_a_brand() -> None:
    parsed = parse_user_text("Rolex 126610 submariner", [])
    assert parsed.brand_tokens == ["Rolex"]


def test_a_brand_that_starts_with_a_number_is_left_alone() -> None:
    # 1017 ALYX 9SM is a real brand; the guard must not eat its first token.
    parsed = parse_user_text("1017 ALYX 9SM buckle boot", [])
    assert parsed.brand_tokens == ["1017", "ALYX"]


def test_two_word_brands_still_survive() -> None:
    assert parse_user_text("Dior Homme General Army Trainer 07", []).brand_tokens == [
        "Dior",
        "Homme",
    ]
    assert parse_user_text("WILLY CHAVARRIA long sleeve", []).brand_tokens == [
        "WILLY",
        "CHAVARRIA",
    ]
