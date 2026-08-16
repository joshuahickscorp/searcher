"""Truth-law enums. Each lives in one place and is used everywhere."""

from __future__ import annotations

from enum import StrEnum


class FactClass(StrEnum):
    """§3.1 observation/inference classification."""

    OBSERVED = "OBSERVED"
    EXTRACTED = "EXTRACTED"
    INFERRED = "INFERRED"
    REPORTED_BY_SOURCE = "REPORTED_BY_SOURCE"
    REPORTED_BY_SELLER = "REPORTED_BY_SELLER"
    USER_SUPPLIED = "USER_SUPPLIED"
    DERIVED = "DERIVED"
    UNRESOLVED = "UNRESOLVED"
    CONTRADICTED = "CONTRADICTED"


class FactOrigin(StrEnum):
    """Where a value came from. Seller origin cannot yield OBSERVED."""

    SENSOR = "sensor"
    EXTRACTOR = "extractor"
    USER = "user"
    SELLER = "seller"
    SOURCE = "source"
    INFERENCE = "inference"
    SYSTEM = "system"


class EvidencePolarity(StrEnum):
    """§3.4."""

    SUPPORTING = "SUPPORTING"
    CONTRADICTORY = "CONTRADICTORY"
    MISSING = "MISSING"
    DUPLICATE = "DUPLICATE"


class SourceOutcome(StrEnum):
    """§3.8. Blocked/failed/unmeasurable must never become SEARCHED_NO_MATCH."""

    SEARCHED_NO_MATCH = "SEARCHED_NO_MATCH"
    SEARCHED_MATCHES_FOUND = "SEARCHED_MATCHES_FOUND"
    BLOCKED_BY_ACCESS = "BLOCKED_BY_ACCESS"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    PARSER_FAILED = "PARSER_FAILED"
    NETWORK_FAILED = "NETWORK_FAILED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    UNMEASURABLE = "UNMEASURABLE"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


class Availability(StrEnum):
    """§16.4."""

    LIVE = "LIVE"
    SOLD = "SOLD"
    RESERVED = "RESERVED"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"


class CampaignState(StrEnum):
    """§10.1."""

    CREATED = "CREATED"
    VALIDATING_INPUT = "VALIDATING_INPUT"
    INGESTING_REFERENCES = "INGESTING_REFERENCES"
    CALIBRATING_REFERENCES = "CALIBRATING_REFERENCES"
    DECOMPOSING_REFERENCES = "DECOMPOSING_REFERENCES"
    FORMING_HYPOTHESES = "FORMING_HYPOTHESES"
    PLANNING_QUERIES = "PLANNING_QUERIES"
    PLANNING_SOURCES = "PLANNING_SOURCES"
    DISCOVERING = "DISCOVERING"
    ACQUIRING = "ACQUIRING"
    NORMALIZING = "NORMALIZING"
    DEDUPLICATING = "DEDUPLICATING"
    BROAD_RETRIEVAL = "BROAD_RETRIEVAL"
    FINE_MATCHING = "FINE_MATCHING"
    AUTHENTICITY_REVIEW = "AUTHENTICITY_REVIEW"
    LIVE_CHECKING = "LIVE_CHECKING"
    RANKING = "RANKING"
    PUBLISHING = "PUBLISHING"
    GAP_ANALYSIS = "GAP_ANALYSIS"
    REPLANNING = "REPLANNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TerminalVerdict(StrEnum):
    """§10.6. Independent of whether any result is Real."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AdoptionDecision(StrEnum):
    """§4.7. Shared with the audit lane."""

    REUSE_AS_PACKAGE = "REUSE_AS_PACKAGE"
    WRAP_WITH_ADAPTER = "WRAP_WITH_ADAPTER"
    PORT_MINIMAL_COMPONENT = "PORT_MINIMAL_COMPONENT"
    VENDOR_FROZEN_SNAPSHOT = "VENDOR_FROZEN_SNAPSHOT"
    REIMPLEMENT_FROM_CONTRACT = "REIMPLEMENT_FROM_CONTRACT"
    DEFER = "DEFER"
    REJECT = "REJECT"


class BucketInternal(StrEnum):
    """§9.14 internal decision."""

    REAL = "real"
    POSSIBLY_REAL = "possibly_real"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"


class BucketPublic(StrEnum):
    """§9.14 public tab. Hidden is not shown. Replica is never Real."""

    REAL = "real"
    POSSIBLY_REAL = "possibly_real"
    REPLICA = "replica"
    HIDDEN = "hidden"


class SourceFamily(StrEnum):
    """Which family of marketplaces a source belongs to."""

    LEGITIMATE = "legitimate"
    REPLICA = "replica"


class HypothesisStatus(StrEnum):
    ACTIVE = "active"
    WEAKENED = "weakened"
    REJECTED = "rejected"
    PROMOTED = "promoted"
    ARCHIVED = "archived"


class QueryType(StrEnum):
    EXACT_NAME = "exact_name"
    ALIAS = "alias"
    TRANSLATED = "translated"
    VISUAL_ATTRIBUTE = "visual_attribute"
    PRODUCT_CODE = "product_code"
    SEASON_DESIGNER = "season_designer"
    SOURCE_SPECIFIC = "source_specific"
    DISCOVERED_TERM = "discovered_term"
    NEGATIVE_RESEARCH = "negative_research"


class QueryStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    EXHAUSTED = "exhausted"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"


class FetchMode(StrEnum):
    """§15.3 ladder. CACHE/HTTP/BROWSER keep Wave 1 values; LIGHT_RENDER is new."""

    CACHE = "cache"
    HTTP = "http"
    LIGHT_RENDER = "light_render"
    BROWSER = "browser"


class ImageRole(StrEnum):
    PRODUCT = "product"
    LABEL = "label"
    SOLE = "sole"
    PACKAGING = "packaging"
    SCREENSHOT = "screenshot"
    UNKNOWN = "unknown"


class ViewHypothesis(StrEnum):
    LATERAL = "lateral"
    MEDIAL = "medial"
    FRONT = "front"
    HEEL = "heel"
    SOLE = "sole"
    LABEL = "label"
    DETAIL = "detail"
    TOP = "top"
    BOX = "box"
    WORN = "worn"
    REAR = "rear"
    UNKNOWN = "unknown"


class HumanReview(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    COMPLETED = "completed"


class Retention(StrEnum):
    SESSION = "session"
    DAYS = "days"
    PERSISTENT = "persistent"


class SourceAdmission(StrEnum):
    ADMITTED = "admitted"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"


class SourceHealthState(StrEnum):
    """§14.6. Health changes planning, never historical results."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    POLICY_DISABLED = "POLICY_DISABLED"
    PARSER_DRIFT = "PARSER_DRIFT"
    UNAVAILABLE = "UNAVAILABLE"


class SourceClass(StrEnum):
    """§14.1 source classes."""

    GENERAL_WEB = "general_web"
    IMAGE_INDEX = "image_index"
    RESALE = "resale"
    AUCTION = "auction"
    CONSIGNMENT = "consignment"
    VINTAGE_ARCHIVE = "vintage_archive"
    REGIONAL = "regional"
    RETAILER_ARCHIVE = "retailer_archive"
    SOLD_ARCHIVE = "sold_archive"
    REFERENCE = "reference"
    USER_URL = "user_url"
    LOCAL_COLLECTION = "local_collection"
    METASEARCH = "metasearch"


class FrontierState(StrEnum):
    PENDING = "pending"
    INFLIGHT = "inflight"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class WorkKind(StrEnum):
    QUERY = "query"
    LISTING = "listing"
    CANONICAL = "canonical"
    GALLERY = "gallery"
    PAGINATION = "pagination"
    LIVE_CHECK = "live_check"
    SITEMAP = "sitemap"


class ExtractionMethod(StrEnum):
    JSON_LD = "json_ld"
    MICRODATA = "microdata"
    RDFA = "rdfa"
    OPEN_GRAPH = "open_graph"
    DOM = "dom"
    GALLERY = "gallery"
    API = "api"
    SITEMAP = "sitemap"
    HTTP_STATUS = "http_status"
    DECLARED = "declared"
    DERIVED = "derived"
    VISION_HOOK = "vision_hook"
    UNKNOWN = "unknown"


class VerificationVerdict(StrEnum):
    """Per-field result of the listing-page verification pass."""

    AGREES = "agrees"
    DISAGREES = "disagrees"
    ABSENT = "absent"


class DegradedLabel(StrEnum):
    """§3.7 allowed fallback labels."""

    CANDIDATE = "CANDIDATE"
    DIAGNOSTIC = "DIAGNOSTIC"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    UNMEASURABLE = "UNMEASURABLE"


class JudgmentKind(StrEnum):
    """The three independent judgments. There is no blended kind."""

    ITEM_MATCH = "ITEM_MATCH"
    AUTHENTICITY_CONFIDENCE = "AUTHENTICITY_CONFIDENCE"
    LISTING_UTILITY = "LISTING_UTILITY"


class PublicEventName(StrEnum):
    """§25.4 public event names."""

    SEARCH_STATE = "search.state"
    SEARCH_PROGRESS = "search.progress"
    SEARCH_COVERAGE = "search.coverage"
    CANDIDATE_DISCOVERED = "candidate.discovered"
    CANDIDATE_NORMALIZED = "candidate.normalized"
    CANDIDATE_PROMOTED = "candidate.promoted"
    CANDIDATE_UPDATED = "candidate.updated"
    RESULT_REAL = "result.real"
    RESULT_POSSIBLY_REAL = "result.possibly_real"
    RESULT_REPLICA = "result.replica"
    RESULT_REMOVED = "result.removed"
    SEARCH_WARNING = "search.warning"
    SEARCH_COMPLETE = "search.complete"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    SKIPPED_IDEMPOTENT = "skipped_idempotent"


class FeedbackVerdict(StrEnum):
    """§22.5 human feedback. Recorded as evidence; never an immediate re-rank."""

    CORRECT_ITEM = "correct_item"
    WRONG_MODEL = "wrong_model"
    LIKELY_REAL = "likely_real"
    UNCERTAIN = "uncertain"
    LIKELY_COUNTERFEIT = "likely_counterfeit"
    LISTING_DEAD = "listing_dead"
    DUPLICATE = "duplicate"
    USEFUL_RESULT = "useful_result"


BLOCKED_SOURCE_OUTCOMES = frozenset(
    {
        SourceOutcome.BLOCKED_BY_ACCESS,
        SourceOutcome.BLOCKED_BY_POLICY,
        SourceOutcome.AUTH_REQUIRED,
        SourceOutcome.RATE_LIMITED,
        SourceOutcome.SOURCE_UNAVAILABLE,
    }
)

FAILED_SOURCE_OUTCOMES = frozenset(
    {
        SourceOutcome.PARSER_FAILED,
        SourceOutcome.NETWORK_FAILED,
        SourceOutcome.UNMEASURABLE,
    }
)

TERMINAL_STATES = frozenset(
    {
        CampaignState.COMPLETE,
        CampaignState.PARTIAL,
        CampaignState.BLOCKED,
        CampaignState.FAILED,
        CampaignState.CANCELLED,
    }
)
