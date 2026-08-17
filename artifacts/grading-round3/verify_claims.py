# ruff: noqa: E501
"""Independent claim checks for the third regrade. Writes verify_claims.json."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any

from searcher.authenticity.completeness import completeness
from searcher.authenticity.profiles import profile_for
from searcher.campaigns.publication import has_usable_listing_link, published_public_bucket
from searcher.contracts.enums import (
    Availability,
    BucketPublic,
    FactClass,
    FactOrigin,
    ImageRole,
    ViewHypothesis,
)
from searcher.contracts.models import (
    CategoryHypothesis,
    LaneStatus,
    ListingCandidate,
    ReferenceAnalysis,
    TargetCluster,
)
from searcher.contracts.primitives import classified
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.hypotheses.item import parse_user_text, seed_portfolio
from searcher.matching.types import IsolatedSubject
from searcher.matching.views import classify_listing_view
from searcher.queries.compiler import compile_queries
from searcher.retrieval.text import self_declared_replica
from searcher.sources.adapters.product import query_slugs
from searcher.sources.engine import DiscoveryEngine
from searcher.sources.expand import expand_index

_TS = parse_utc("2007-06-15T12:00:00+00:00")

OUT = Path("artifacts/grading-round3/verify_claims.json")

LEAKED_13 = [
    "This is fake.",
    "スーパーコピー レプリカ",
    "Dior Homme GAT dupe",
    "Inspired by Dior Homme General Army Trainer",
    "Dior Homme GAT superfake",
    "Dior Homme GAT PK God factory",
    "Dior Homme GAT UA batch",
    "Dior Homme GAT 1：1",
    "not genuine",
    "Dior Homme GAT mirror batch",
    "Dior Homme GAT homage",
    "repsneaker quality",
    "Unauthorized replica 1:1 of the original trainer",
]

LEAKED_ROUND_TWO = [
    "1st copy",
    "first copy",
    "super copy",
    "super-copy",
    "god factory",
    "not the authentic piece",
    "isn't authentic",
    "ain't genuine",
    "not the real thing",
    "replika",
    "réplique",
    "imitazione",
    "imitation",
    "re\u200bplica",
    "r e p l i c a",
    "1/1 pair",
    "1-1 quality",
    "one to one",
    "same as retail",
    "best batch",
    "repfam",
    "high quality copy",
    "mirror",
    "from the factory",
    "not orig",
    "this isn't the authentic pair",
    "counter feit",
    "super  copy",
    "UA quality",
    "PK factory",
]

GENUINE = [
    "Dior Homme General Army Trainer",
    "Black wool coat with faux fur collar",
    "Vintage fake leather jacket",
    "Authentic Prada pumps size 38 1/2",
    "WILLY CHAVARRIA 無地 ロングスリーブカットソー",
    "Comme des Garcons SHIRT x Supreme loop collar shirt",
    "Copy of the original receipt included",
    "comes with copy of the original invoice",
]

# Seller language that is not in either committed regression list.
EXTRA_BEYOND_REGRESSION = [
    "AAA+",
    "aaa quality",
    "this is a rep",
    "unauthorised replica",
    "not original item",
    "rep sneakers",
    "not legit",
    "this is not legit",
    "god batch",
    "retail batch",
    "rep1ica",
    "repliсa",  # Cyrillic 'с'
    "comes with replica box",
    "quality replica",
    "mirror copy",
    "1:1",
    "reps",
    "dup",
]


class _Decision:
    def __init__(self, public: BucketPublic, reason_codes: list[str] | None = None) -> None:
        self.decision = type("D", (), {"public": public})()
        self.hard_vetoes: list[str] = []
        self.reason_codes: list[str] = list(reason_codes or [])


def _candidate(url: str, title: str = "plain long sleeve") -> ListingCandidate:
    return ListingCandidate(
        candidate_id="c1",
        canonical_url=url,
        source_adapter="kind",
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )


def check_replica_phrases() -> dict[str, Any]:
    missed_13 = [t for t in LEAKED_13 if not self_declared_replica(t)]
    missed_30 = [t for t in LEAKED_ROUND_TWO if not self_declared_replica(t)]
    false_pos = [t for t in GENUINE if self_declared_replica(t)]
    extra_detected = [t for t in EXTRA_BEYOND_REGRESSION if self_declared_replica(t)]
    extra_missed = [t for t in EXTRA_BEYOND_REGRESSION if not self_declared_replica(t)]
    receipt_ok = self_declared_replica("Copy of the original receipt included") is False
    return {
        "claim": "thirty extra replica phrasings detected; receipt copy is not a replica",
        "leaked_13": len(LEAKED_13),
        "leaked_round_two": len(LEAKED_ROUND_TWO),
        "missed_13": missed_13,
        "missed_30": missed_30,
        "false_positives_on_genuine": false_pos,
        "receipt_copy_not_replica": receipt_ok,
        "extra_beyond_regression_detected": extra_detected,
        "extra_beyond_regression_missed": extra_missed,
        "holds": not missed_13 and not missed_30 and not false_pos and receipt_ok,
    }


def check_publish_requires_link() -> dict[str, Any]:
    rows = []
    for url in ["", None, "javascript:alert(1)", "data:text/html,x", "/products/1"]:
        candidate = _candidate("" if url is None else url)
        if url is None:
            candidate = candidate.model_copy(update={"canonical_url": ""})
        usable = has_usable_listing_link(candidate)
        published = {
            bucket.value: published_public_bucket(_Decision(bucket), candidate)
            for bucket in (BucketPublic.REAL, BucketPublic.POSSIBLY_REAL)
        }
        rows.append({"url": url, "usable": usable, "published": published})
    honest = _candidate("https://shop.kind.co.jp/products/8001001141404")
    honest_pub = published_public_bucket(_Decision(BucketPublic.POSSIBLY_REAL), honest)
    missing = published_public_bucket(_Decision(BucketPublic.REAL), None)
    leak = any(
        pub != BucketPublic.HIDDEN.value
        for row in rows
        for pub in row["published"].values()
    )
    return {
        "claim": "public bucket requires usable http(s) link; null/javascript stay hidden",
        "bad_urls": rows,
        "honest_https_publishes": honest_pub,
        "missing_candidate": missing,
        "holds": (
            not leak
            and honest_pub == BucketPublic.POSSIBLY_REAL.value
            and missing == BucketPublic.HIDDEN.value
        ),
    }


def check_generic_profile() -> dict[str, Any]:
    profile = profile_for("garment")
    vocabulary = {view.value for view in ViewHypothesis}
    full, missing_full = completeness(profile=profile, present_views=set(profile.expected_views))
    empty, missing_empty = completeness(profile=profile, present_views=set())
    footwear = profile_for("footwear")
    return {
        "claim": "generic profile no longer expects view 'unknown'; completeness not pinned at 0.4",
        "expected_views": list(profile.expected_views),
        "unknown_in_expected": "unknown" in profile.expected_views,
        "all_expected_are_classifier_views": all(v in vocabulary for v in profile.expected_views),
        "full_completeness": full,
        "empty_completeness": empty,
        "empty_missing": missing_empty,
        "full_missing": missing_full,
        "footwear_still_has_sole": "sole" in footwear.expected_views,
        "holds": (
            "unknown" not in profile.expected_views
            and bool(profile.expected_views)
            and full == 1.0
            and empty < 0.5
        ),
    }


def check_view_classification() -> dict[str, Any]:
    def subject(area: float, width: int = 1024, height: int = 1024) -> IsolatedSubject:
        return IsolatedSubject(
            image_id="i1",
            png=b"",
            bbox=(0, 0, width, height),
            subject_area=area,
            relevant=True,
            role=ImageRole.PRODUCT.value,
            width=width,
            height=height,
        )

    garment_front = classify_listing_view(subject(0.64), category="garment")
    garment_detail = classify_listing_view(subject(0.12), category="garment")
    footwear = classify_listing_view(subject(0.64), category="footwear")
    unknown = classify_listing_view(subject(0.64), category=None)
    return {
        "claim": "garment filling the frame reads front, not heel",
        "garment_full_frame": garment_front.view.value,
        "garment_close_crop": garment_detail.view.value,
        "footwear_full_frame": footwear.view.value,
        "unknown_category": unknown.view.value,
        "holds": (
            garment_front.view is ViewHypothesis.FRONT
            and garment_detail.view is ViewHypothesis.DETAIL
            and footwear.view in {ViewHypothesis.HEEL, ViewHypothesis.LATERAL}
            and unknown.view is ViewHypothesis.FRONT
        ),
    }


def check_size_not_brand() -> dict[str, Any]:
    parsed = parse_user_text(
        "PRADA(プラダ) ハイヒールパンプス ブラック サイズ 38 1/2", ["PRADA"]
    )
    brand_slug = query_slugs(" ".join(parsed.brand_tokens))
    # What query_slugs would do if size leaked into the brand string.
    leaked_slug = query_slugs("PRADA 38")
    analysis = ReferenceAnalysis(
        analysis_id=new_id(),
        search_id="s",
        primary_cluster=TargetCluster(cluster_id=new_id(), confidence=0.5),
        category_hypotheses=[CategoryHypothesis(category="footwear", confidence=0.4)],
        lanes=[LaneStatus(name="DENSE_FEATURES", available=False, blocked=True)],
        promotion_blocked=True,
    )
    hyps = seed_portfolio(
        search_id="s",
        text="PRADA(プラダ) ハイヒールパンプス ブラック サイズ 38 1/2",
        tags=["PRADA"],
        analysis=analysis,
    )
    queries = compile_queries(hyps, analysis, user_terms=[
        "PRADA(プラダ) ハイヒールパンプス ブラック サイズ 38 1/2",
        "PRADA",
    ])
    slugs = []
    for q in queries:
        slugs.extend(query_slugs(q.query_text))
    prada_38 = [s for s in slugs if s == "prada-38" or s.endswith("-38") or s == "38"]
    return {
        "claim": "size is not part of brand; shop is not asked for prada-38",
        "brand_tokens": parsed.brand_tokens,
        "model_tokens": parsed.model_tokens,
        "size_in_brand": "38" in parsed.brand_tokens,
        "brand_slugs": brand_slug,
        "legacy_prada_38_slug": leaked_slug,
        "compiled_query_texts": [q.query_text for q in queries],
        "compiled_slugs": sorted(set(slugs)),
        "prada_38_or_size_slugs": prada_38,
        "holds": (
            parsed.brand_tokens == ["PRADA"]
            and "38" not in parsed.brand_tokens
            and "prada-38" not in slugs
            and not prada_38
        ),
    }


def check_index_ranks_before_cap() -> dict[str, Any]:
    products = []
    target_handle = "8003001995070"
    target_index = 103  # 0-based; feed position 104
    for i in range(120):
        if i == target_index:
            products.append(
                {
                    "id": i + 1,
                    "handle": target_handle,
                    "title": "ハイヒールパンプス",
                    "vendor": "PRADA",
                    "product_type": "パンプス",
                    "tags": "brand_PRADA:プラダ",
                    "images": [{"src": "https://cdn.example.test/prada.jpg"}],
                    "variants": [{"price": "38000", "available": True}],
                }
            )
        else:
            products.append(
                {
                    "id": i + 1,
                    "handle": f"filler-{i:04d}",
                    "title": f"other brand tee {i}",
                    "vendor": "OtherBrand",
                    "product_type": "tee",
                    "tags": "",
                    "images": [{"src": f"https://cdn.example.test/{i}.jpg"}],
                    "variants": [{"price": "1000", "available": True}],
                }
            )
    body = json.dumps({"products": products}).encode()
    url = "https://shop.kind.co.jp/collections/all/products.json"
    user_text = "PRADA(プラダ) ハイヒールパンプス ブラック サイズ 38 1/2"
    tags = ["PRADA"]
    ranked = expand_index(
        url=url,
        body=body,
        listing_prefixes=("/products/",),
        allowed_hosts=("shop.kind.co.jp",),
        per_index_cap=24,
        per_campaign_cap=48,
        query_texts=[user_text, *tags],
    )
    unranked = expand_index(
        url=url,
        body=body,
        listing_prefixes=("/products/",),
        allowed_hosts=("shop.kind.co.jp",),
        per_index_cap=24,
        per_campaign_cap=48,
        query_texts=(),
    )
    ranked_handles = [m.handle for m in ranked.taken]
    unranked_handles = [m.handle for m in unranked.taken]
    target_url = f"https://shop.kind.co.jp/products/{target_handle}"
    ranked_urls = [m.url for m in ranked.taken]
    intent_src = inspect.getsource(DiscoveryEngine._intent_terms)
    return {
        "claim": "index expansion ranks members against user text and tags before the cap",
        "members_found": ranked.members_found,
        "ranked_taken": len(ranked.taken),
        "ranked_first_handle": ranked_handles[0] if ranked_handles else None,
        "ranked_first_url": ranked_urls[0] if ranked_urls else None,
        "target_rank_among_taken": (
            ranked_handles.index(target_handle) + 1 if target_handle in ranked_handles else None
        ),
        "target_in_unranked_first_24": target_handle in unranked_handles,
        "unranked_first_handle": unranked_handles[0] if unranked_handles else None,
        "intent_terms_includes_user_text": "text" in intent_src and "tags" in intent_src,
        "query_texts_used": [user_text, *tags],
        "holds": (
            ranked.members_found == 120
            and len(ranked.taken) == 24
            and ranked_handles
            and ranked_handles[0] == target_handle
            and ranked_urls[0] == target_url
            and target_handle not in unranked_handles
        ),
    }


def check_flagship_behaviour_21() -> dict[str, Any]:
    src = Path("scripts/flagship_acceptance.py").read_text(encoding="utf-8")
    hardcoded = 'rows.append(row(21, "resume after forced interruption",\n                    "met"'
    reports_not_eval = '"not evaluable"' in src and "this harness does not interrupt" in src
    receipt = json.loads(
        Path("artifacts/searcher-flagship-matched.receipt.json").read_text(encoding="utf-8")
    )
    b21 = next(r for r in receipt["behaviours"] if r["n"] == "21")
    summary = receipt["summary"]
    return {
        "claim": "acceptance harness reports behaviour 21 as not evaluable; score is 20 of 24",
        "source_hardcodes_met": hardcoded in src,
        "source_says_not_evaluable": reports_not_eval,
        "stored_b21": b21,
        "stored_summary": summary,
        "holds": (
            hardcoded not in src
            and reports_not_eval
            and b21["verdict"] == "not evaluable"
            and summary["met"] == 20
            and summary["of"] == 24
        ),
    }


def check_docs_and_threshold_language() -> dict[str, Any]:
    root = Path(".")
    files_nine = [
        "ARCHITECTURE.md",
        "CLAIMS.md",
        "LIMITATIONS.md",
        "README.md",
        "docs/OPERATING.md",
        "docs/architecture/API.md",
        "docs/architecture/EMBEDDINGS.md",
        "docs/architecture/MATCHING_AND_AUTHENTICITY.md",
        "web/index.html",
    ]
    exist = {f: (root / f).is_file() for f in files_nine}
    shortlist_hits = {}
    for path in [
        "CLAIMS.md",
        "LIMITATIONS.md",
        "README.md",
        "SEARCHER_BUCKET_POLICY.md",
        "docs/architecture/EMBEDDINGS.md",
        "src/searcher/core/embedding_gateway.py",
    ]:
        text = (root / path).read_text(encoding="utf-8")
        shortlist_hits[path] = {
            "shortlist_cut": "shortlist cut" in text.lower() or "shortlist cut" in text,
            "identity_gate": "identity gate" in text.lower(),
            "70_percent": "70%" in text or "0.7" in text,
            "0.86": "0.86" in text,
        }
    gateway = (root / "src/searcher/core/embedding_gateway.py").read_text(encoding="utf-8")
    return {
        "claim": "pair threshold documented as shortlist cut; nine docs exist",
        "nine_exist": exist,
        "all_nine_exist": all(exist.values()),
        "shortlist_language": shortlist_hits,
        "gateway_comment_has_shortlist": "shortlist cut" in gateway,
        "gateway_comment_has_70": "70%" in gateway,
    }


def main() -> int:
    report = {
        "git_sha": os.popen("git rev-parse HEAD").read().strip(),
        "replica_phrases": check_replica_phrases(),
        "publish_requires_link": check_publish_requires_link(),
        "generic_profile": check_generic_profile(),
        "view_classification": check_view_classification(),
        "size_not_brand": check_size_not_brand(),
        "index_ranks_before_cap": check_index_ranks_before_cap(),
        "flagship_behaviour_21": check_flagship_behaviour_21(),
        "docs_and_threshold": check_docs_and_threshold_language(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    summary = {
        k: (v.get("holds") if isinstance(v, dict) and "holds" in v else "n/a")
        for k, v in report.items()
        if k != "git_sha"
    }
    print(json.dumps({"sha": report["git_sha"], "holds": summary, "wrote": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
