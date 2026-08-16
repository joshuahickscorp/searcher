"""Marketplace adapters registered disabled pending review. No outbound fetch."""

from __future__ import annotations

from dataclasses import dataclass

from searcher.contracts.enums import FetchMode, SourceAdmission, SourceFamily, SourceOutcome
from searcher.contracts.models import FetchResult, QueryVariant, SourceManifest
from searcher.core.ids import new_id
from searcher.sources.adapters.generic_page import GenericPageAdapter
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.fetch_modes import FetchedDocument
from searcher.sources.manifest import build_manifest


@dataclass(frozen=True, slots=True)
class PendingSpec:
    source_id: str
    domain: str
    source_family: SourceFamily
    source_class: str
    notes: str
    open_question: str
    languages: tuple[str, ...] = ("en",)
    robots_policy: str = "not fetched live in this wave; adapter is disabled"


def pending_manifest(spec: PendingSpec) -> SourceManifest:
    return build_manifest(
        source_id=spec.source_id,
        adapter=spec.source_id,
        domain=spec.domain,
        access_method="http_get",
        admission_status=SourceAdmission.REVIEW_REQUIRED,
        allowed_use="none until review completes",
        source_class=spec.source_class,
        source_family=spec.source_family,
        capabilities=["listing_fetch"],
        robots_policy=spec.robots_policy,
        languages=list(spec.languages),
        enabled=False,
        open_question=spec.open_question,
        known_limitations=[spec.notes],
    )


class PendingReviewAdapter(GenericPageAdapter):
    """Admission record only. Discover and fetch never leave the process."""

    spec: PendingSpec

    def __init__(self, spec: PendingSpec) -> None:
        self.spec = spec
        super().__init__(pending_manifest(spec))

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del query, cursor
        return DiscoveryPageResult(
            [],
            [],
            None,
            SourceOutcome.BLOCKED_BY_POLICY.value,
            self.spec.open_question,
        )

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        return FetchedDocument(
            result=FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=SourceOutcome.BLOCKED_BY_POLICY,
                classification_note=self.spec.open_question,
            ),
            body=b"",
            headers={},
            final_url=url,
        )


DEPOP = PendingSpec(
    source_id="depop",
    domain="www.depop.com",
    source_family=SourceFamily.LEGITIMATE,
    source_class="resale",
    notes="Cloudflare interstitial on robots/terms 2026-08-16.",
    open_question="Can robots.txt and terms be fetched without a challenge?",
    robots_policy="robots.txt was behind a Cloudflare interstitial on 2026-08-16",
)

GRAILED = PendingSpec(
    source_id="grailed",
    domain="www.grailed.com",
    source_family=SourceFamily.LEGITIMATE,
    source_class="resale",
    notes="Cloudflare block on robots/terms 2026-08-16.",
    open_question="Can robots.txt and terms be fetched without a challenge?",
    robots_policy="robots.txt was Cloudflare-blocked on 2026-08-16",
)

VESTIAIRE = PendingSpec(
    source_id="vestiaire",
    domain="www.vestiairecollective.com",
    source_family=SourceFamily.LEGITIMATE,
    source_class="consignment",
    notes="Cloudflare interstitial on robots/terms 2026-08-16.",
    open_question="Can robots.txt and terms be fetched without a challenge?",
    robots_policy="robots.txt was behind a Cloudflare interstitial on 2026-08-16",
)

TAOBAO = PendingSpec(
    source_id="taobao",
    domain="www.taobao.com",
    source_family=SourceFamily.REPLICA,
    source_class="regional",
    notes="robots allow /list/*; item URLs with query strings are Disallow.",
    open_question="Is there an admitted item-page path that does not require login?",
    languages=("zh", "en"),
    robots_policy="Allow: /list/* ; Disallow: /*?* (2026-08-16 research)",
)

WEIDIAN = PendingSpec(
    source_id="weidian",
    domain="weidian.com",
    source_family=SourceFamily.REPLICA,
    source_class="regional",
    notes="robots.txt redirected to an abnormal 404 page on 2026-08-16.",
    open_question="Is there a fetchable robots.txt and an admitted public listing path?",
    languages=("zh", "en"),
    robots_policy="robots.txt redirected to h5.weidian.com/m/abnormal/404.html on 2026-08-16",
)

YUPOO = PendingSpec(
    source_id="yupoo",
    domain="yupoo.com",
    source_family=SourceFamily.REPLICA,
    source_class="regional",
    notes="robots.txt and terms were not fetched in this wave. No outbound host.",
    open_question="What does robots.txt allow, and is album HTML an admitted listing path?",
    languages=("zh", "en"),
)


class DepopAdapter(PendingReviewAdapter):
    def __init__(self) -> None:
        super().__init__(DEPOP)


class GrailedAdapter(PendingReviewAdapter):
    def __init__(self) -> None:
        super().__init__(GRAILED)


class VestiaireAdapter(PendingReviewAdapter):
    def __init__(self) -> None:
        super().__init__(VESTIAIRE)


class TaobaoAdapter(PendingReviewAdapter):
    def __init__(self) -> None:
        super().__init__(TAOBAO)


class WeidianAdapter(PendingReviewAdapter):
    def __init__(self) -> None:
        super().__init__(WEIDIAN)


class YupooAdapter(PendingReviewAdapter):
    def __init__(self) -> None:
        super().__init__(YUPOO)
