"""Internal matching records. Public contracts stay in searcher.contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.contracts.enums import ViewHypothesis
from searcher.contracts.models import ListingCandidate
from searcher.matching.ontology import CategoryOntology


@dataclass
class IsolatedSubject:
    image_id: str
    png: bytes
    bbox: tuple[int, int, int, int]
    subject_area: float
    relevant: bool
    role: str
    reason: str = ""
    width: int = 0
    height: int = 0


@dataclass
class ViewGuess:
    image_id: str
    view: ViewHypothesis
    confidence: float
    method: str


@dataclass
class ExtractedPart:
    name: str
    image_id: str
    view: str
    count: int | None
    region: tuple[float, float, float, float] | None
    descriptor: str | None
    confidence: float
    notes: list[str] = field(default_factory=list)


@dataclass
class StructuredDescriptor:
    image_id: str
    width: int
    height: int
    aspect: float
    subject_area: float
    centroid: tuple[float, float]
    eyelet_count: int
    panel_count: int
    seam_count: int
    outsole_ratio: float
    sole_to_upper: float
    heel_aspect: float
    heel_cut: str
    heel_angle: float
    logo_xy: tuple[float, float] | None
    logo_kind: str | None
    tread_kind: str
    label_hash: str | None
    dominant_rgb: tuple[float, float, float]
    smoothness: float
    keypoints: int


@dataclass
class CorrespondenceResult:
    inlier_ratio: float
    match_count: int
    inlier_count: int
    method: str
    mirrored: bool
    residual: float
    notes: list[str] = field(default_factory=list)


@dataclass
class GeometryResult:
    score: float
    sole_to_upper_delta: float
    heel_angle_delta: float
    aspect_delta: float
    panel_delta: int
    eyelet_delta: int
    notes: list[str] = field(default_factory=list)


@dataclass
class EnrichedCandidate:
    candidate: ListingCandidate
    pngs: dict[str, bytes]
    ocr_terms: list[str] = field(default_factory=list)
    isolated: list[IsolatedSubject] = field(default_factory=list)
    views: list[ViewGuess] = field(default_factory=list)
    parts: list[ExtractedPart] = field(default_factory=list)
    descriptors: dict[str, StructuredDescriptor] = field(default_factory=dict)
    cluster_id: str | None = None
    image_family_ids: list[str] = field(default_factory=list)
    stock_family_ids: list[str] = field(default_factory=list)


@dataclass
class MatchWorkspace:
    ontology: CategoryOntology
    reference_pngs: dict[str, bytes]
    reference_descriptors: dict[str, StructuredDescriptor]
    reference_parts: list[ExtractedPart]
    reference_views: list[ViewGuess]
