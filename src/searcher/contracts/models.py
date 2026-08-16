"""Canonical §9 records and supporting types. Names match the Bible exactly."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator, model_validator

from searcher.contracts.enums import (
    Availability,
    BucketInternal,
    BucketPublic,
    CampaignState,
    FactClass,
    FactOrigin,
    FetchMode,
    HumanReview,
    HypothesisStatus,
    ImageRole,
    QueryStatus,
    QueryType,
    Retention,
    SourceAdmission,
    SourceFamily,
    SourceHealthState,
    SourceOutcome,
    TerminalVerdict,
    ViewHypothesis,
)
from searcher.contracts.primitives import (
    ClassifiedFact,
    ItemMatchJudgment,
    ListingUtilityJudgment,
    NormalizedField,
    PartMatch,
    PublicExplanation,
    ScoreInterval,
    ScoreWithEvidence,
    SearcherModel,
)
from searcher.core.time import UtcDateTime


class SearchConstraints(SearcherModel):
    category: str | None = None
    brand: str | None = None
    size: str | None = None
    colour: str | None = None
    price_max: Decimal | None = None
    currency: str | None = None
    region: str | None = None
    condition: str | None = None


class IntentBudget(SearcherModel):
    wall_seconds: int
    source_limit: int
    page_limit: int
    browser_page_limit: int
    image_limit: int
    model_call_limit: int
    byte_limit: int
    monetary_limit: Decimal | None = None


class PrivacySettings(SearcherModel):
    retention: Retention = Retention.SESSION
    training_opt_in: bool = False

    @field_validator("training_opt_in")
    @classmethod
    def no_silent_training(cls, value: bool) -> bool:
        if value:
            raise ValueError("training_opt_in defaults to false and is not enabled in wave 1")
        return value


class ReferenceImageRef(SearcherModel):
    reference_image_id: str
    content_digest: str


class SearchIntent(SearcherModel):
    """§9.1"""

    search_id: str
    created_at: UtcDateTime
    images: list[ReferenceImageRef] = Field(default_factory=list)
    text: str | None = None
    tags: list[str] = Field(default_factory=list)
    constraints: SearchConstraints = Field(default_factory=SearchConstraints)
    budget: IntentBudget
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)


class TextObservation(SearcherModel):
    text: str
    region: tuple[float, float, float, float] | None = None
    confidence: float
    fact_class: FactClass = FactClass.EXTRACTED
    origin: FactOrigin = FactOrigin.EXTRACTOR
    kind: str = "unknown"
    injection_candidate: bool = False

    @model_validator(mode="after")
    def seller_not_observed(self) -> TextObservation:
        if self.origin == FactOrigin.SELLER and self.fact_class == FactClass.OBSERVED:
            raise ValueError("seller-reported value cannot be constructed as OBSERVED")
        # GUARD: OCR / extractor output can never be recorded as OBSERVED (§3.1).
        if self.origin == FactOrigin.EXTRACTOR and self.fact_class == FactClass.OBSERVED:
            raise ValueError("OCR text can never become an OBSERVED fact")
        return self


class ImageQuality(SearcherModel):
    blur: float = 0.0
    compression: float = 0.0
    occlusion: float = 0.0
    subject_area: float = 0.0
    resolution: float = 0.0
    perspective: float = 0.0
    lighting: float = 0.0
    background_interference: float = 0.0
    text_visibility: float = 0.0
    part_visibility: float = 0.0
    weight: float = 0.0
    usable_for: list[str] = Field(default_factory=list)


class ReferenceCrop(SearcherModel):
    """§9.3"""

    crop_id: str
    parent_image_id: str
    region: tuple[float, float, float, float]
    object_hypothesis: str
    part_hypothesis: str | None = None
    view_hypothesis: ViewHypothesis = ViewHypothesis.UNKNOWN
    confidence: float
    mask_ref: str | None = None
    feature_ref: str | None = None
    fact_class: FactClass = FactClass.INFERRED


class ReferenceDerived(SearcherModel):
    normalized_image: str | None = None
    thumbnail: str | None = None
    masks: list[str] = Field(default_factory=list)
    crops: list[ReferenceCrop] = Field(default_factory=list)
    ocr: list[TextObservation] = Field(default_factory=list)
    feature_sets: list[str] = Field(default_factory=list)


class ReferenceImage(SearcherModel):
    """§9.2"""

    reference_image_id: str
    content_digest: str
    media_type: str
    byte_length: int
    width: int
    height: int
    orientation: str = "unknown"
    colour_space: str = "unknown"
    source: str = "user_upload"
    privacy_state: str = "private"
    derived: ReferenceDerived = Field(default_factory=ReferenceDerived)
    quality: ImageQuality = Field(default_factory=ImageQuality)
    fact_class: FactClass = FactClass.USER_SUPPLIED


class BeliefUpdate(SearcherModel):
    at: UtcDateTime
    previous_value: str | None
    new_value: str | None
    reason: str
    evidence_ref: str | None = None


class Belief(SearcherModel):
    """§9.4 supporting type. Value, confidence, evidence, families, history."""

    value: str | None
    confidence: float
    fact_class: FactClass
    origin: FactOrigin
    evidence: list[str] = Field(default_factory=list)
    independent_source_families: int = 0
    update_history: list[BeliefUpdate] = Field(default_factory=list)

    @model_validator(mode="after")
    def seller_not_observed(self) -> Belief:
        if self.origin == FactOrigin.SELLER and self.fact_class == FactClass.OBSERVED:
            raise ValueError("seller-reported value cannot be constructed as OBSERVED")
        return self


class AliasBelief(SearcherModel):
    alias: str
    language: str | None = None
    belief: Belief


class Uncertainty(SearcherModel):
    question: str
    impact: str
    missing_evidence: list[str] = Field(default_factory=list)


class PartSignature(SearcherModel):
    name: str
    embedding: str | None = None
    geometry: str | None = None


class VisualSignatureGlobal(SearcherModel):
    silhouette: str | None = None
    embedding: str | None = None
    colour_distribution: str | None = None


class CrossImageLink(SearcherModel):
    image_a: str
    image_b: str
    similarity: float
    method: str


class VisualSignature(SearcherModel):
    """§9.5"""

    global_features: VisualSignatureGlobal = Field(default_factory=VisualSignatureGlobal)
    parts: list[PartSignature] = Field(default_factory=list)
    distinctive_relations: list[str] = Field(default_factory=list)
    uncertain_features: list[str] = Field(default_factory=list)
    texture: str | None = None
    ocr_terms: list[str] = Field(default_factory=list)
    logo_candidates: list[str] = Field(default_factory=list)
    correspondence: list[CrossImageLink] = Field(default_factory=list)
    descriptor_kind: str = "cheap_histogram"
    learned_embedding_available: bool = False


class ItemHypothesis(SearcherModel):
    """§9.4"""

    hypothesis_id: str
    search_id: str
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    category: str
    brand: Belief
    model_name: Belief
    line: Belief
    designer: Belief
    season: Belief
    year: Belief
    colourway: Belief
    materials: list[Belief] = Field(default_factory=list)
    product_codes: list[Belief] = Field(default_factory=list)
    aliases: list[AliasBelief] = Field(default_factory=list)
    translations: list[AliasBelief] = Field(default_factory=list)
    visual_signature: VisualSignature = Field(default_factory=VisualSignature)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    uncertainties: list[Uncertainty] = Field(default_factory=list)
    posterior: float = 0.0


class QueryVariant(SearcherModel):
    """§9.6"""

    query_id: str
    hypothesis_id: str
    round: int
    language: str
    query_text: str
    query_type: QueryType
    origin_evidence: list[str] = Field(default_factory=list)
    expected_gain: float = 0.0
    cost_estimate: float = 0.0
    status: QueryStatus = QueryStatus.QUEUED
    source_coverage: list[str] = Field(default_factory=list)
    overlap: float = 0.0
    family: str = ""
    provisional: bool = False
    translation_record: dict[str, object] | None = None


class RatePolicy(SearcherModel):
    requests_per_minute: int = 30
    burst: int = 5
    concurrent: int = 1


class Admission(SearcherModel):
    status: SourceAdmission
    basis: str


class SourcePlan(SearcherModel):
    """§9.7"""

    source_plan_id: str
    source_adapter: str
    query_ids: list[str] = Field(default_factory=list)
    admission: Admission
    rate_policy: RatePolicy = Field(default_factory=RatePolicy)
    auth_mode: str = "public_only"
    fetch_modes: list[FetchMode] = Field(default_factory=lambda: [FetchMode.CACHE])
    expected_fields: list[str] = Field(
        default_factory=lambda: ["title", "url", "image", "price", "size", "availability"]
    )
    budget: dict[str, int] = Field(default_factory=dict)


class FetchAttempt(SearcherModel):
    """§9.8"""

    attempt_id: str
    source_id: str
    url: str
    canonical_url: str
    started_at: UtcDateTime
    ended_at: UtcDateTime
    mode: FetchMode
    status: SourceOutcome
    http_status: int | None = None
    content_digest: str | None = None
    bytes: int = 0
    retry_parent: str | None = None
    runtime_attestation: str | None = None
    error_class: str | None = None


class ListingImage(SearcherModel):
    """§9.10"""

    listing_image_id: str
    candidate_id: str
    remote_url: str
    content_digest: str | None = None
    perceptual_hash: str | None = None
    width: int | None = None
    height: int | None = None
    role: ImageRole = ImageRole.UNKNOWN
    duplicate_family_id: str | None = None
    feature_ref: str | None = None
    fact_class: FactClass = FactClass.REPORTED_BY_SOURCE


class ListingCandidate(SearcherModel):
    """§9.9"""

    candidate_id: str
    canonical_url: str
    source_adapter: str
    source_listing_id: str | None = None
    title: ClassifiedFact | None = None
    description: ClassifiedFact | None = None
    seller_reported_brand: ClassifiedFact | None = None
    seller_reported_model: ClassifiedFact | None = None
    price_original: Decimal | None = None
    currency_original: str | None = None
    size_original: str | None = None
    condition_reported: ClassifiedFact | None = None
    availability: Availability = Availability.UNKNOWN
    seller_metadata: dict[str, object] = Field(default_factory=dict)
    images: list[ListingImage] = Field(default_factory=list)
    structured_data: dict[str, object] = Field(default_factory=dict)
    field_records: dict[str, NormalizedField] = Field(default_factory=dict)
    first_seen_at: UtcDateTime
    last_checked_at: UtcDateTime
    source_evidence: list[str] = Field(default_factory=list)
    cluster_id: str | None = None
    explanation: PublicExplanation = Field(default_factory=PublicExplanation)
    language: str | None = None

    @model_validator(mode="after")
    def seller_fields_are_reported(self) -> ListingCandidate:
        for field_name in (
            "seller_reported_brand",
            "seller_reported_model",
            "condition_reported",
        ):
            fact = getattr(self, field_name)
            if fact is None:
                continue
            if fact.origin == FactOrigin.SELLER and fact.fact_class == FactClass.OBSERVED:
                raise ValueError("seller-reported value cannot be constructed as OBSERVED")
        return self


class MatchEvidence(SearcherModel):
    """§9.11. ITEM_MATCH judgment lives here; not authenticity, not utility."""

    match_evidence_id: str
    candidate_id: str
    hypothesis_id: str
    global_visual: ScoreWithEvidence
    text_identity: ScoreWithEvidence
    part_correspondence: list[PartMatch] = Field(default_factory=list)
    geometry: ScoreWithEvidence
    material: ScoreWithEvidence
    colourway: ScoreWithEvidence
    cross_image_consistency: ScoreWithEvidence
    metadata_consistency: ScoreWithEvidence
    hard_support: list[str] = Field(default_factory=list)
    soft_support: list[str] = Field(default_factory=list)
    hard_contradictions: list[str] = Field(default_factory=list)
    soft_contradictions: list[str] = Field(default_factory=list)
    missing_views: list[str] = Field(default_factory=list)
    item_match_distribution: ScoreInterval
    judgment: ItemMatchJudgment | None = None
    explanation: PublicExplanation = Field(default_factory=PublicExplanation)

    @model_validator(mode="after")
    def bind_item_match_judgment(self) -> MatchEvidence:
        if self.judgment is None:
            self.judgment = ItemMatchJudgment(interval=self.item_match_distribution)
        elif self.judgment.interval != self.item_match_distribution:
            raise ValueError("ITEM_MATCH judgment interval must match item_match_distribution")
        return self


class AuthenticityEvidence(SearcherModel):
    """§9.12. AUTHENTICITY_CONFIDENCE judgment; independent of item match."""

    authenticity_evidence_id: str
    candidate_id: str
    reference_class: str
    construction_consistency: ScoreWithEvidence
    label_and_code_consistency: ScoreWithEvidence
    logo_and_hardware_consistency: ScoreWithEvidence
    material_consistency: ScoreWithEvidence
    photo_set_consistency: ScoreWithEvidence
    image_originality: ScoreWithEvidence
    source_and_seller_signal: ScoreWithEvidence
    provenance_signal: ScoreWithEvidence
    price_anomaly: ScoreWithEvidence
    hard_support: list[str] = Field(default_factory=list)
    hard_contradictions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    authenticity_distribution: ScoreInterval
    authority_ceiling: str = "provisional"
    explanation: PublicExplanation = Field(default_factory=PublicExplanation)

    @property
    def judgment(self) -> Any:
        from searcher.contracts.primitives import AuthenticityJudgment

        return AuthenticityJudgment(
            interval=self.authenticity_distribution,
            authority_ceiling=self.authority_ceiling,
        )


class ListingUtility(SearcherModel):
    """§9.13. LISTING_UTILITY judgment; independent of match and authenticity."""

    live: bool
    size_match: float | None = None
    region_match: float | None = None
    condition_match: float | None = None
    price_fit: float | None = None
    shipping_known: bool = False
    description_quality: float = 0.0
    image_coverage: float = 0.0
    last_checked_at: UtcDateTime
    utility_score: float
    explanation: PublicExplanation = Field(default_factory=PublicExplanation)

    @property
    def judgment(self) -> ListingUtilityJudgment:
        score = max(0.0, min(1.0, self.utility_score))
        return ListingUtilityJudgment(
            interval=ScoreInterval(mean=score, lower_bound=score, upper_bound=score),
            live=self.live,
        )


class BucketDecisionFields(SearcherModel):
    internal: BucketInternal
    public: BucketPublic


class BucketDecision(SearcherModel):
    """§9.14"""

    candidate_id: str
    decision: BucketDecisionFields
    policy_version: str
    item_match_lower_bound: float
    authenticity_lower_bound: float
    evidence_completeness: float
    hard_vetoes: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    human_review: HumanReview = HumanReview.NOT_REQUIRED
    receipt_ref: str | None = None
    explanation: PublicExplanation = Field(default_factory=PublicExplanation)

    @model_validator(mode="after")
    def veto_and_liveness_rules(self) -> BucketDecision:
        if self.hard_vetoes and self.decision.public in {
            BucketPublic.REAL,
            BucketPublic.POSSIBLY_REAL,
        }:
            raise ValueError("a candidate with a hard veto cannot enter either public tab")
        if (
            self.decision.public == BucketPublic.REAL
            and self.explanation.live_status is not None
            and self.explanation.live_status is not Availability.LIVE
        ):
            raise ValueError("a dead listing cannot become Real")
        return self


class SearchCampaign(SearcherModel):
    """§9.15"""

    search_id: str
    state: CampaignState
    state_version: int
    intent_ref: str
    hypothesis_ids: list[str] = Field(default_factory=list)
    query_ids: list[str] = Field(default_factory=list)
    source_run_ids: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    result_ids: list[str] = Field(default_factory=list)
    budget_used: dict[str, object] = Field(default_factory=dict)
    coverage: dict[str, object] = Field(default_factory=dict)
    novelty_history: list[float] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    terminal_status: TerminalVerdict | None = None
    terminal_reason: str | None = None
    search_exhaustion_receipt: str | None = None
    fixture_name: str | None = None


class NextEvidenceRequest(SearcherModel):
    request_id: str
    target: str
    reason: str
    expected_gain: float = 0.0


class TargetCluster(SearcherModel):
    cluster_id: str
    image_ids: list[str] = Field(default_factory=list)
    crop_ids: list[str] = Field(default_factory=list)
    role: str = "primary"
    relation: str = "same_item_multiple_views"
    confidence: float = 0.0
    notes: list[str] = Field(default_factory=list)


class ViewInventoryEntry(SearcherModel):
    crop_id: str
    view: ViewHypothesis
    confidence: float
    fact_class: FactClass = FactClass.INFERRED


class PartInventoryEntry(SearcherModel):
    crop_id: str
    part: str
    confidence: float
    fact_class: FactClass = FactClass.INFERRED


class CategoryHypothesis(SearcherModel):
    category: str
    confidence: float
    fact_class: FactClass = FactClass.INFERRED
    evidence: list[str] = Field(default_factory=list)


class EvidenceGap(SearcherModel):
    gap: str
    impact: str
    request: str | None = None


class LaneStatus(SearcherModel):
    name: str
    available: bool
    blocked: bool = False
    degraded: bool = False
    reason: str = ""
    authority_ceiling: str = "none"


class ReferenceAnalysis(SearcherModel):
    """§11.9 output. Later waves consume this record, not donor types."""

    analysis_id: str
    search_id: str
    images: list[ReferenceImage] = Field(default_factory=list)
    primary_cluster: TargetCluster
    alternate_clusters: list[TargetCluster] = Field(default_factory=list)
    quality_map: dict[str, ImageQuality] = Field(default_factory=dict)
    view_inventory: list[ViewInventoryEntry] = Field(default_factory=list)
    part_inventory: list[PartInventoryEntry] = Field(default_factory=list)
    text_and_marks: list[TextObservation] = Field(default_factory=list)
    visual_signature: VisualSignature = Field(default_factory=VisualSignature)
    category_hypotheses: list[CategoryHypothesis] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    lanes: list[LaneStatus] = Field(default_factory=list)
    promotion_blocked: bool = False
    donor_invoked: bool = False
    donor_version: str | None = None
    uncertainties: list[Uncertainty] = Field(default_factory=list)


class LiveStatus(SearcherModel):
    availability: Availability
    checked_at: UtcDateTime
    destination_verified: bool = False
    http_status: int | None = None
    outcome: SourceOutcome | None = None
    note: str | None = None


class SourceHealth(SearcherModel):
    source_id: str
    last_outcome: SourceOutcome
    consecutive_failures: int = 0
    circuit_open: bool = False
    last_checked_at: UtcDateTime
    state: SourceHealthState = SourceHealthState.HEALTHY
    breaker_open_until: UtcDateTime | None = None
    last_block_class: str | None = None
    last_success_at: UtcDateTime | None = None


class SourceManifest(SearcherModel):
    """Wave 1 §29.7 fields plus the §14.2 adapter manifest (schema 1.1)."""

    source_id: str
    adapter: str
    domain: str
    access_method: str
    admission_status: SourceAdmission
    allowed_use: str
    retention: str = "temporary"
    thumbnail_policy: str = "cache-temporary"
    publication_boundary: str = "link-only"
    refresh_policy: str = "on-demand"
    rights_review_status: str = "fixture"
    name: str = ""
    version: str = "1.0.0"
    source_class: str = "general_web"
    capabilities: list[str] = Field(default_factory=list)
    public_access: bool = True
    authentication: str = "none"
    robots_policy: str = ""
    terms_review_status: SourceAdmission | None = None
    rate_policy: RatePolicy = Field(default_factory=RatePolicy)
    fetch_modes: list[FetchMode] = Field(default_factory=lambda: [FetchMode.HTTP])
    fields: list[str] = Field(default_factory=list)
    retention_policy: dict[str, str] = Field(default_factory=dict)
    health_check: str = "get_home"
    known_limitations: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["en"])
    enabled: bool = True
    disallowed_path_prefixes: list[str] = Field(default_factory=list)
    open_question: str | None = None
    robots_url: str | None = None
    sitemap_urls: list[str] = Field(default_factory=list)
    listing_path_prefixes: list[str] = Field(default_factory=list)
    source_family: SourceFamily = SourceFamily.LEGITIMATE

    @model_validator(mode="after")
    def fill_defaults(self) -> SourceManifest:
        if not self.name:
            self.name = self.source_id
        if self.terms_review_status is None:
            self.terms_review_status = self.admission_status
        return self


class DiscoveryPage(SearcherModel):
    page_id: str
    search_id: str
    source_id: str
    query_id: str | None = None
    url: str
    content_digest: str | None = None
    cursor: str | None = None
    outcome: SourceOutcome
    fetched_at: UtcDateTime | None = None


class FetchResult(SearcherModel):
    attempt_id: str
    url: str
    outcome: SourceOutcome
    content_digest: str | None = None
    bytes: int = 0
    http_status: int | None = None
    canonical_url: str = ""
    mode: FetchMode = FetchMode.HTTP
    content_type: str | None = None
    error_class: str | None = None
    from_cache: bool = False
    retry_after_seconds: float | None = None
    redirected_from: str | None = None
    classification_note: str | None = None
    final_url: str | None = None


class RawListing(SearcherModel):
    source_adapter: str
    url: str
    payload: dict[str, object] = Field(default_factory=dict)
    content_digest: str
    fetched_at: UtcDateTime
